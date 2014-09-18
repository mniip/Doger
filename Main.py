import socket, errno, time, sys, traceback, threading
sys.dont_write_bytecode = True
import Global, Config, Irc, Logger

Logger.log("m", "Started Doger")
for instance in Config.config["instances"]:
	Global.manager_queue.put(("Spawn", instance))
Irc.manager()
Logger.log("me", "Manager returned")
