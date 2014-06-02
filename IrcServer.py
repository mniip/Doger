import socket, time

import Irc

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
		self.connection = socket.create_connection((self.host, self.port), None)
		self.connection.settimeout(0.0)
		self.buffer = ''
		self.send("NICK", self.nick)
		self.send("USER", self.nick, "*", "*", self.nick)
		self.send("NS", "identify " + self.password)

	def __init__(self, remote, nick, password):
		host, port = remote.split(":")
		self.host = host
		self.port = port
		self.nick = nick
		self.password = password
		self.connection = None
		self.unseen = []
		self.lastsend = 0
		self.connect()
