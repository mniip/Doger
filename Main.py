import socket, errno, time, sys, traceback, threading
import Config
from IrcServer import *

lock = threading.Lock()
lock.acquire()

def thread(nick, channels):
	irc = IrcServer(nick)
	irc.autojoin = channels
	while True:
		try:
			irc.loop()
			break
		except Exception as e:
			type, value, tb = sys.exc_info()
			print(nick + " ===============")
			traceback.print_tb(tb)
			print(repr(e))
			print(nick + " ===============")
	irc.disconnect()

for nick in Config.config["nicks"]:
	t = threading.Thread(target = thread, args = (nick, Config.config["nicks"][nick]))
	t.setDaemon(True)
	t.start()

lock.acquire()
