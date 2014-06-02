import socket, errno, time, sys
import Transactions, Hooks
from IrcServer import *

serv = IrcServer(sys.argv[1], sys.argv[2], sys.argv[3])
serv.autojoin = sys.argv[4].split(",")
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
