import socket, errno, time, sys, traceback
from IrcServer import *

conf = eval(open('config.py', 'r').read())

irc = IrcServer(conf)
while irc.running:
	try:
		irc.loop()
	except Exception as e:
		type, value, tb = sys.exc_info()
		traceback.print_tb(tb)
		print(repr(e))
