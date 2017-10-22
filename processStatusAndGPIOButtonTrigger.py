#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 2017 hidenorly
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import io
import codecs
from optparse import OptionParser, OptionValueError
import os
import time
import json

existRpiGpio = True
try:
	import RPi.GPIO as GPIO
except ImportError:
	existRpiGpio = False
	pass

from pyExecUtil import PyExecUtil
from pyTaskManager import PyTask,PyTaskManager


# for Python 3.x
try:
	#sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
	sys.stdout = codecs.getwriter("utf8")(sys.stdout.buffer)
except AttributeError:
	pass

class ConfigUtil(object):
	@staticmethod
	def findData(jsonData, searchKey):
		result = []

		for key, val in jsonData.items():
			if key.find(searchKey)!=-1:
				result.append(val)

		return result


class GPIOUtil(object):
	@staticmethod
	def initialize():
		if existRpiGpio:
			GPIO.setmode(GPIO.BCM)

	@staticmethod
	def terminate():
		if existRpiGpio:
			GPIO.cleanup()

	@staticmethod
	def setupOutput(port):
		if port!=None:
			if existRpiGpio:
				GPIO.setup(port, GPIO.OUT)

	@staticmethod
	def setupInput(port, enablePullUp):
		if port!=None:
			if existRpiGpio:
				if enablePullUp:
					GPIO.setup(port, GPIO.IN, pull_up_down = GPIO.PUD_UP)
				else:
					GPIO.setup(port, GPIO.IN)

	@staticmethod
	def getGPIStatus(port):
		result = False
		if port!=None:
			if existRpiGpio:
				result = GPIO.input(port)

		return result

	@staticmethod
	def setGPOStatus(port, value):
		if port!=None:
			if existRpiGpio:
				GPIO.output(port, value)

class Watcher(PyTask):
	def __init__(self, description = "", watchTargets=[], period = 5):
		super(Watcher, self).__init__(description)
		self._watchTargets = watchTargets
		self._period = period

	def onExecute(self):
		try:
			while( not self.mStopRunning ):
				self.check()
				if not self.mStopRunning:
					time.sleep(self._period)
		except KeyboardInterrupt:
			return

	def check(self):
		print("overide here")


class ProcessWatcher(Watcher):
	PATH_PROC = "/proc"

	@staticmethod
	def isProcessExisting(command):
		found = False
		if os.path.exists(ProcessWatcher.PATH_PROC):
			pids = [pid for pid in os.listdir(ProcessWatcher.PATH_PROC) if pid.isdigit()]
			for pid in pids:
				try:
					cmd = open(os.path.join(ProcessWatcher.PATH_PROC, pid, "cmdline"), "rb").read()
					found |= (command in cmd)
					if found:
						break
				except IOError:
					continue

		return found

	def __init__(self, description = "ProcessWatcher", watchTargets=[], period = 5):
		super(ProcessWatcher, self).__init__(description, watchTargets, period)
		for aProcessCfg in self._watchTargets:
			if "port" in aProcessCfg:
				port = aProcessCfg["port"]
				GPIOUtil.setupOutput( port )
			else:
				aProcessCfg["port"] = None
			if not "active" in aProcessCfg:
				aProcessCfg["active"] = True
			status = False
			if "command" in aProcessCfg:
				status = self.isProcessExisting(aProcessCfg["command"])
			aProcessCfg["_prevStatus"] = aProcessCfg["status"] = status

	def check(self):
		for aProcessCfg in self._watchTargets:
			if("command" in aProcessCfg) and aProcessCfg["command"]:
				aProcessCfg["status"] = self.isProcessExisting(aProcessCfg["command"])
				if aProcessCfg["_prevStatus"] != aProcessCfg["status"]:
					aProcessCfg["_prevStatus"] = aProcessCfg["status"]
					self.doIt(aProcessCfg, aProcessCfg["status"])

	def doIt(self, aProcessCfg, status):
		# Set GPO
		value = False
		if status:
			value = aProcessCfg["active"]
		else:
			value = not aProcessCfg["active"]
		if "port" in aProcessCfg:
			GPIOUtil.setGPOStatus(aProcessCfg["port"], value)

		# Exec command
		execCmd = ""
		if status:
			if "onFound" in aProcessCfg:
				execCmd = aProcessCfg["onFound"]
		else:
			if "onLost" in aProcessCfg:
				execCmd = aProcessCfg["onLost"]

		if execCmd:
			cmd = PyExecUtil(execCmd)
			_timeout = 0
			if "timeout" in aProcessCfg:
				_timeout = aProcessCfg["timeout"]
			cmd.execute(timeout=_timeout)


class ButtonWatcher(Watcher):
	DEBOUNCED_COUNT = 3

	def __init__(self, description = "ButtonWatcher", watchTargets=[], period = 0.1):
		super(ButtonWatcher, self).__init__(description, watchTargets, period/self.DEBOUNCED_COUNT)

		# Setup GPI
		for aButtonCfg in self._watchTargets:
			if "port" in aButtonCfg:
				port = aButtonCfg["port"]
				enablePullUp = False
				if "pull-up" in aButtonCfg:
					enablePullUp =  aButtonCfg["pull-up"]
				GPIOUtil.setupInput( port, enablePullUp )
			else:
				aButtonCfg["port"] = None
			if not "active" in aButtonCfg:
				aButtonCfg["active"] = False
			aButtonCfg["_count"] = 0
			aButtonCfg["_prevStatus"] = GPIOUtil.getGPIStatus(aButtonCfg["port"])
			if not "execute" in aButtonCfg:
				aButtonCfg["execute"] = ""
			aButtonCfg["_flagDoIt"] = False

	def check(self):
		for aButtonCfg in self._watchTargets:
			curStatus = GPIOUtil.getGPIStatus(aButtonCfg["port"])
			if aButtonCfg["_prevStatus"] != curStatus:
				aButtonCfg["_prevStatus"] = curStatus
				aButtonCfg["_count"] = 0
				if aButtonCfg["_flagDoIt"] == True:
					self.onActive(aButtonCfg)
					aButtonCfg["_flagDoIt"] = False
			else:
				if curStatus == aButtonCfg["active"]:
					aButtonCfg["_count"] = aButtonCfg["_count"] + 1
					if aButtonCfg["_count"] > self.DEBOUNCED_COUNT:
						aButtonCfg["_flagDoIt"] = True

	def onActive(self, aButtonCfg):
		if aButtonCfg["execute"]:
			cmd = PyExecUtil(aButtonCfg["execute"])
			cmd.execute(timeout=aButtonCfg["timeout"])

if __name__ == '__main__':
	parser = OptionParser()

	parser.add_option("-c", "--config", action="store", type="string", dest="config", default="config.json", help="Specify config.json path")
	parser.add_option("-p", "--period", action="store", type="float", dest="period", default="5", help="Specify polling process period (sec)")
	parser.add_option("-d", "--debounced", action="store", type="float", dest="debounced", default="0.15", help="Specify button deboucned period (sec)")

	(options, args) = parser.parse_args()

	# setup
	GPIOUtil.initialize()

	# load config
	f = open(options.config, "r")
	config = json.load(f)
	f.close()

	# Set Process Watcher
	watchProcesses = ConfigUtil.findData(config, "process")
	watchButtons = ConfigUtil.findData(config, "button")

	taskMan = PyTaskManager(2);
	taskMan.addTask(ProcessWatcher(watchTargets = watchProcesses, period = options.period))
	taskMan.addTask(ButtonWatcher(watchTargets = watchButtons, period = options.debounced))
	taskMan.executeAll()
	taskMan.finalize()
