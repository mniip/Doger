import socket, time

import Irc, Hooks

class IrcServer:
	def send(self, *args):
		print(repr(args))
		t = self.lastsend - time.time() + 0.25
		if t > 0:
			time.sleep(t)
		self.connection.sendall(Irc.compile(*args) + "\n")
		self.lastsend = time.time()

	def unread(self, data):
		self.unseen.extend(data)

	def read(self):
		if len(self.unseen):
			print("Unseen: " + repr(self.unseen[0]))
			return self.unseen.pop(0)
		while self.buffer.find('\n') == -1:
			data = self.connection.recv(4096)
			self.buffer += data
		line, self.buffer = self.buffer.split('\n', 1)
		print(repr(Irc.parse(line.rstrip('\r'))))
		return Irc.parse(line.rstrip('\r'))

	def connect(self):
		self.connection = socket.create_connection((self.config["host"], self.config["port"]), None)
		self.connection.settimeout(None)
		self.buffer = ''
		self.send("NICK", self.config["nick"])
		self.nick = self.config["nick"]
		self.send("USER", self.config["user"], "*", "*", self.config["rname"])
		self.send("NS", "identify " + self.config["password"])

	def disconnect(self):
		self.send("QUIT")
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

	def __init__(self, config):
		self.config = config
		self.connection = None
		self.unseen = []
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
		return self.config["admins"].get(hostmask, False)
