import socket, time, random

import Irc, Hooks, Config

class IrcServer:
	def send(self, *args):
		print(self.nick + ": " + Irc.compile(*args))
		t = self.lastsend - time.time() + 0.25
		if t > 0:
			time.sleep(t)
		self.connection.sendall(Irc.compile(*args) + "\n")
		self.lastsend = time.time()

	def unread(self, data):
		self.unseen.extend(data)

	def read(self):
		if len(self.unseen):
			return self.unseen.pop(0)
		while self.buffer.find('\n') == -1:
			data = self.connection.recv(4096)
			self.buffer += data
		line, self.buffer = self.buffer.split('\n', 1)
		return Irc.parse(line.rstrip('\r'))

	def connect(self):
		host = random.choice(socket.gethostbyname_ex(Config.config["host"])[2])
		self.connection = socket.create_connection((host, Config.config["port"]), None)
		self.connection.settimeout(None)
		self.buffer = ''
		self.send("NICK", self.nick)
		self.send("USER", Config.config["user"], "*", "*", Config.config["rname"])
		self.send("NS", "identify " + Config.config["password"])

	def disconnect(self):
		self.send("QUIT")
		self.connection.close()
		self.connection = None
	
	def is_ignored(self, host):
		r = self.ignored.get(host, None)
		if r:
			if r < time.time():
				del self.ignored[host]
				return False
			return True
		return False

	def ignore(self, host, duration):
		self.ignored[host] = time.time() + duration

	def __init__(self, nick):
		self.connection = None
		self.unseen = []
		self.autojoin = []
		self.nick = nick
		self.lastsend = 0
		self.running = True
		self.ignored = {}
		self.flood_score = {}
		self.connect()

	def loop(self):
		while self.running:
			cmd = self.read()
			if cmd[1][0] != '_':
				hook = Hooks.hooks.get(cmd[1], None)
				if hook:
					hook(self, cmd[0], *cmd[2:])

	def is_admin(self, hostmask):
		return Config.config["admins"].get(hostmask, False)
