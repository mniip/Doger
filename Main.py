import socket, errno, time, sys, traceback, threading
import Global, Config, Irc

for instance in Config.config["instances"]:
	Global.manager_queue.put(("Spawn", instance))
Irc.manager()
