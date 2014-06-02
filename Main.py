import socket, errno, time, sys, traceback
import Hooks
from IrcServer import *

conf = eval(open('config.py', 'r').read())

serv = IrcServer(conf["server"], conf["nick"], conf["password"])
serv.autojoin = conf["autojoin"].split(",")
while True:
	try:
		cmd = serv.read()
		try:
			name = "numeric_" + str(int(cmd[1]))
		except ValueError:
			name = cmd[1]
		if name[0] != '_':
			hook = getattr(Hooks, name, None)
			if hook:
				hook(serv, cmd[0], *cmd[2:])
	except socket.error as e:
		if e[0] == errno.EAGAIN:
			time.sleep(0.01)
		else:
			print(repr(e))
			break
	except Exception as e:
		type, value, tb = sys.exc_info()
		traceback.print_tb(tb)
		ret = repr(e)
