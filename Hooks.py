# coding=utf8
import traceback, sys, re, time

import Irc, Transactions, Commands

hooks = {}

def end_of_motd(serv, *_):
	for channel in serv.autojoin:
		serv.send("JOIN", channel)
hooks["376"] = end_of_motd

def ping(serv, *_):
	serv.send("PONG")
hooks["PING"] = ping

class Request(object):
	def __init__(self, serv, target, source):
		self.serv = serv
		self.target = target
		self.source = source
		self.nick = Irc.get_nickname(source)

	def reply(self, text):
		self.serv.send("PRIVMSG", self.target, self.nick + ": " + text)

	def reply_private(self, text):
		self.serv.send("PRIVMSG", self.nick, self.nick + ": " + text)

	def say(self, text):
		self.serv.send("PRIVMSG", self.target, text)

def message(serv, source, target, text):
	host = Irc.get_host(source)
	if host == "lucas.fido.pw":
		m = re.match(r"Wow!  (\S*) just sent you Ð\d*\.", text)
		if not m:
			m = re.match(r"Wow!  (\S*) sent Ð\d* to Doger!", text)
		if m:
			nick = m.group(1)
			address = Transactions.deposit_address(Irc.toupper(nick))
			serv.send("PRIVMSG", "fido", "withdraw " + address.encode("utf8"))
			serv.send("PRIVMSG", nick, "Your tip has been withdrawn to your account and will appear in %balance soon")
	elif text[0] == '%' or target == serv.nick:
		if serv.is_ignored(host):
			print(serv.nick + ": (ignored) <" + Irc.get_nickname(source) + "> " + text)
			return
		print(serv.nick + ": <" + Irc.get_nickname(source) + "> " + text)
		t = time.time()
		score = serv.flood_score.get(host, (t, 0))
		score = max(score[1] + score[0] - t, 0) + 4
		if score > 40 and not serv.is_admin(source):
			serv.ignore(host, 240)
			serv.send("PRIVMSG", Irc.get_nickname(source), "You're sending commands too quickly. Your host is ignored for 240 seconds")
			return
		serv.flood_score[host] = (t, score)
		if text[0] == '%':
			text = text[1:]
		src = Irc.get_nickname(source)
		if target == serv.nick:
			reply = src
		else:
			reply = target
		if text.find(" ") == -1:
			command = text
			args = []
		else:
			command, args = text.split(" ", 1)
			args = args.split(" ")
		if command[0] != '_':
			cmd = Commands.commands.get(command, None)
			if not cmd.__doc__ or cmd.__doc__.find("admin") == -1 or serv.is_admin(source):
				if cmd:
					req = Request(serv, reply, source)
					try:
						ret = cmd(req, args)
					except Exception as e:
						type, value, tb = sys.exc_info()
						traceback.print_tb(tb)
						req.reply(repr(e))
hooks["PRIVMSG"] = message
