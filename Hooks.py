# coding=utf8
import traceback, sys, re, time, threading, Queue, socket

import Irc, Config, Transactions, Commands, Config, Global

hooks = {}

def end_of_motd(identity, *_):
	for channel in Config.config["identities"][identity]:
		Irc.identity_send(identity, "JOIN", channel)
hooks["376"] = end_of_motd

def ping(identity, *_):
	Irc.identity_send(identity, "PONG")
hooks["PING"] = ping

class Request(object):
	def __init__(self, identity, target, source):
		self.identity = identity
		self.target = target
		self.source = source
		self.nick = Irc.get_nickname(source)

	def privmsg(self, targ, text):
		while len(text) > 350:
			Irc.identity_send(self.identity, "PRIVMSG", targ, text[:349])
			text = text[350:]
		Irc.identity_send(self.identity, "PRIVMSG", targ, text)

	def reply(self, text):
		self.privmsg(self.target, self.nick + ": " + text)

	def reply_private(self, text):
		self.privmsg(self.nick, self.nick + ": " + text)

	def say(self, text):
		self.privmsg(self.target, text)

def message(identity, source, target, text):
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
	elif text[0] == '%' or target == identity:
		if Irc.is_ignored(host):
			print(identity + ": (ignored) <" + Irc.get_nickname(source) + "> " + text)
			return
		print(identity + ": <" + Irc.get_nickname(source) + "> " + text)
		t = time.time()
		score = Global.flood_score.get(host, (t, 0))
		score = max(score[1] + score[0] - t, 0) + 10
		if score > 80 and not Irc.is_admin(source):
			Irc.ignore(host, 240)
			Irc.identity_send("PRIVMSG", Irc.get_nickname(source), "You're sending commands too quickly. Your host is ignored for 240 seconds")
			return
		Global.flood_score[host] = (t, score)
		if text[0] == '%':
			text = text[1:]
		src = Irc.get_nickname(source)
		if target == identity:
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
			if not cmd.__doc__ or cmd.__doc__.find("admin") == -1 or Irc.is_admin(source):
				if cmd:
					req = Request(identity, reply, source)
					t = threading.Thread(target = cmd, args = (req, args))
					t.start()
hooks["PRIVMSG"] = message

def error(serv, *_):
	raise socket.error()
hooks["ERROR"] = error

def whois_ident(identity, _, __, target, account, ___):
	Global.lastwhois[identity] = account
hooks["330"] = whois_ident

def whois_end(identity, _, __, target, ___):
	try:
		nick, q = Global.whois_queue[identity].get(False)
		if Irc.equal_nicks(target, nick):
			q.put(Global.lastwhois[identity], True)
		else:
			print(identity + ": WHOIS reply for " + target + " but queued " + nick + " returning None")
			q.put(None, True)
		Global.lastwhois[identity] = None
	except Queue.Empty:
		print(identity + ": WHOIS reply but nothing queued")
hooks["318"] = whois_end
