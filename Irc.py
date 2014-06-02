import socket, errno, time
from string import maketrans

ircupper = maketrans(
	"abcdefghijklmnopqrstuvwxyz[]~\\",
	"ABCDEFGHIJKLMNOPQRSTUVWXYZ{}^|")

def parse(cmd):
	data = cmd.split(" ")
	if data[0][0] != ':':
		data.insert(0, None)
	else:
		data[0] = data[0][1:]
	for i in range(1, len(data)):
		if data[i][0] == ':':
			data[i:] = [(" ".join(data[i:]))[1:]]
			break
	return data

def get_nickname(hostmask):
	return hostmask.split("!", 1)[0]

def toupper(nickname):
	return nickname.translate(ircupper)

def compile(*args):
	data = list(args)
	data[-1] = ':' + data[-1]
	return " ".join(data)

def account(serv, nick):
	serv.send("WHOIS", nick)
	account = None
	unseen = []
	while True:
		try:
			cmd = serv.read()
			if cmd[1] == "318" and cmd[3] == nick:
				break
			elif cmd[1] == "330" and toupper(cmd[3]) == toupper(nick):
				account = cmd[4]
			else:
				unseen.append(cmd)
		except socket.error as e:
			if e[0] == errno.EAGAIN:
				time.sleep(0.01)
			else:
				raise e
	serv.unread(unseen)
	return account

def anyone(serv, nick):
	serv.send("WHO", nick)
	exists = False
	unseen = []
	while True:
		try:
			cmd = serv.read()
			if cmd[1] == "315" and cmd[3] == nick:
				break
			elif cmd[1] == "352" and toupper(cmd[7]) == toupper(nick):
				exists = True
			else:
				unseen.append(cmd)
		except socket.error as e:
			if e[0] == errno.EAGAIN:
				time.sleep(0.01)
			else:
				raise e
	serv.unread(unseen)
	return exists
