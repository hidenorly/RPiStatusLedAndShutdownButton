# What's this?

This is IoT device helper for Raspberry Pi, etc.
Simple expected usage is for Status LED &amp; Shutdown Button.

* Check the process status and indicate the status by GPO (expecting LED).
* Check the GPIO Button and execute external program such as ```shutdown -h now```

If you create IoT device with Raspberry Pi, this is very useful because you don't need to login SSH to shutdown the device and whether your process is working or not.

# How to use

## Configuration

```config.json
{
	"button_shutdown":{
		"port": 18,
		"pull-up": true,
		"active": false,
		"execute": "shutdown -h now",
		"timeout": 0
	},
	"process_apache2":{
		"port": 23,
		"active": true,
		"command": "apache2",
		"onFound": "",
		"onLost": "service restart apache2",
		"timeout": 0
	}
}
```

* When GPIO 18 is LOW, it executes ```shutdown -h now```.
* During ```apache2``` process is existing, GPIO23 is HIGH. (If lost, it will be LOW.)
* When ```apache2``` process is lost, it executes ```service restart apache2```


// timeout: 0 means infinite (No time out), or you can set it as [sec].
