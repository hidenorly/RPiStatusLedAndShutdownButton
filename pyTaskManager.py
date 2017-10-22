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

from threading import Thread, Lock
import time

# TaskManager and Task definitions

class PyTask(object):
	description = ""
	taskCompleCallback = None
	running = False
	mStopRunning = False
	_thread = None

	def __init__(self, description = ""):
		self.description = description
		self.running = False
		self._taskManager = None
		self._taskCompleCallback = None
		self.mStopRunning = False
		self._thread = None

	def execute(self, args):
		self.mStopRunning = False
		self.running = True
		self.onExecute()
		self._doneTask()
		self.running = False
		self.mStopRunning = False

	def onExecute(self):
		# override me
		for i in range(50):
			time.sleep(0.1)
			if True == self.mStopRunning:
				break

	def cancel(self):
		if self.running:
			self.mStopRunning = True

	def finalize(self):
		self.running = False

	def _doneTask(self):
		if( (None!=self._taskCompleCallback) and (None!=self._taskManager) ):
			self._taskCompleCallback(self)

class PyTaskManager:
	def __init__(self, numOfThread = 4):
		self.tasks = []
		self.numOfThread = numOfThread
		self.threads = []
		self.mutexTasks = Lock()
		self.mutexThreads = Lock()
		self._stoppingTask = False

	def addTask(self, aTask):
		aTask._taskManager = self
		aTask._taskCompleCallback = self._onTaskCompletion

		self.mutexTasks.acquire()
		try:
			self.tasks.append( aTask )
		finally:
			self.mutexTasks.release()

	def cancelTask(self, aTask):
		self.mutexTasks.acquire()
		self.mutexThreads.acquire()
		try:
			if aTask.running:
				aTask.cancel()
			self.tasks.remove(aTask)

			_t = None
			for t in self.threads:
				if t == aTask._thread:
					_t = t
			if( None!=_t ):
				self.threads.remove(_t)

		finally:
			self.mutexThreads.release()
			self.mutexTasks.release()

	def executeAll(self):
		self._stoppingTask = False

		self.mutexTasks.acquire()
		self.mutexThreads.acquire()
		try:
			for aTask in self.tasks:
				if( (False == aTask.running) and (len(self.threads) < self.numOfThread) ):
					t = Thread(target = aTask.execute, args = (aTask,))
					if(t!=None):
						self.threads.append(t)
						aTask.running = True
						aTask._thread = t
						t.start()
		finally:
			self.mutexThreads.release()
			self.mutexTasks.release()

	def isRunning(self):
		result = False

		self.mutexThreads.acquire()
		try:
			if len(self.threads) > 0:
				result = True
		finally:
			self.mutexThreads.release()

		return result

	def isRemainingTasks(self):
		result = False

		self.mutexTasks.acquire()
		try:
			if len(self.tasks) > 0:
				result = True
		finally:
			self.mutexTasks.release()

		return result

	def _onTaskCompletion(self, aTask):
		self.cancelTask( aTask )
		if self._stoppingTask == False:
			self.executeAll()

	def stopAll(self):
		self._stoppingTask = True

		while( self.isRunning() ):
			self.mutexTasks.acquire()
			try:
				for aTask in self.tasks:
					if aTask.running:
						aTask.cancel()
			finally:
				self.mutexTasks.release()
			time.sleep(0.1)

	def finalize(self):
		while( self.isRemainingTasks() or self.isRunning() ):
			if ( self.isRunning() ):
				time.sleep(0.1)
			else:
				break
