# coding=utf8
import traceback, sys, re, time, threading, Queue, socket, subprocess

import Irc, Config, Transactions, Commands, Config, Global, Logger

hooks = {}

def end_of_motd(instance, *_):
	Global.instances[instance].can_send.set()
	Logger.log("c", instance + ": End of motd, joining " + " ".join(Config.config["instances"][instance]))
	for channel in Config.config["instances"][instance]:
		Irc.instance_send(instance, ("JOIN", channel))
hooks["376"] = end_of_motd

def ping(instance, *_):
	Irc.instance_send(instance, ("PONG",), priority = 0)
hooks["PING"] = ping

class Request(object):
	def __init__(self, instance, target, source, text):
		self.instance = instance
		self.target = target
		self.source = source
		self.nick = Irc.get_nickname(source)
		self.text = text

	def privmsg(self, targ, text, priority = None):
		Logger.log("c", self.instance + ": %s <- (pri=%s) %s " % (targ, str(priority),  text))
		for i in xrange(0, len(text), 350):
			if priority:
				Irc.instance_send(self.instance, ("PRIVMSG", targ, text[i:i+350]), priority = priority)
			else:
				Irc.instance_send(self.instance, ("PRIVMSG", targ, text[i:i+350]))

	def reply(self, text):
		if self.nick == self.target:
			self.privmsg(self.target, self.nick + ": " + text, priority = 10)
		else:
			self.privmsg(self.target, self.nick + ": " + text)

	def reply_private(self, text):
		self.privmsg(self.nick, self.nick + ": " + text, priority = 10)

	def say(self, text):
		if self.nick == self.target:
			self.privmsg(self.target, text, priority = 10)
		else:
			self.privmsg(self.target, text)

class FakeRequest(Request):
	def __init__(self, req, target, text):
		self.instance = req.instance
		self.target = req.target
		self.source = req.source
		self.nick = target
		self.text = text
		self.realnick = req.nick

	def privmsg(self, targ, text, priority = None):
		Logger.log("c", self.instance + ": %s <- %s " % (targ, text))
		for i in xrange(0, len(text), 350):
			if priority:
				Irc.instance_send(self.instance, ("PRIVMSG", targ, text[i:i+350]), priority = priority)
			else:
				Irc.instance_send(self.instance, ("PRIVMSG", targ, text[i:i+350]))

	def reply(self, text):
		self.privmsg(self.target, self.realnick + " [reply] : " + text)

	def reply_private(self, text):
		self.privmsg(self.target, self.realnick + " [reply_private]: " + text)

	def say(self, text):
		self.privmsg(self.target, text)

def run_command(cmd, req, arg):
	try:
		cmd(req, arg)
	except Exception as e:
		req.reply(repr(e))
		type, value, tb = sys.exc_info()
		Logger.log("ce", "ERROR in " + req.instance + " : " + req.text)
		Logger.log("ce", repr(e))
		Logger.log("ce", "".join(traceback.format_tb(tb)))
		Logger.irclog("Error while executing '%s' from '%s': %s" % (req.text, req.nick, repr(e)))
		Logger.irclog("".join(traceback.format_tb(tb)).replace("\n", " || "))
		del tb

def message(instance, source, target, text):
	host = Irc.get_host(source)
	if text == "\x01VERSION\x01":
		p = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout = subprocess.PIPE)
		hash, _ = p.communicate()
		hash = hash.strip()
		p = subprocess.Popen(["git", "diff", "--quiet"])
		changes = p.wait()
		if changes:
			hash += "[+]"
		version = "Doger by mniip, version " + hash
		Irc.instance_send(instance, ("NOTICE", Irc.get_nickname(source), "\x01VERSION " + version + "\x01"), priority = 20)
	else:
		commandline = None
		if target == instance:
			commandline = text
		if text[0] == Config.config["prefix"]:
			commandline = text[1:]
		if commandline:
			if Irc.is_ignored(host):
				Logger.log("c", instance + ": %s <%s ignored> %s " % (target, Irc.get_nickname(source), text))
				return
			Logger.log("c", instance + ": %s <%s> %s " % (target, Irc.get_nickname(source), text))
			if Config.config.get("ignore", None):
				t = time.time()
				score = Global.flood_score.get(host, (t, 0))
				score = max(score[1] + score[0] - t, 0) + Config.config["ignore"]["cost"]
				if score > Config.config["ignore"]["limit"] and not Irc.is_admin(source):
					Logger.log("c", instance + ": Ignoring " + host)
					Irc.ignore(host, Config.config["ignore"]["timeout"])
					Irc.instance_send(instance, ("PRIVMSG", Irc.get_nickname(source), "You're sending commands too quickly. Your host is ignored for 240 seconds"))
					return
				Global.flood_score[host] = (t, score)
			src = Irc.get_nickname(source)
			if target == instance:
				reply = src
			else:
				reply = target
			commandline = commandline.rstrip(" \t")
			if commandline.find(" ") == -1:
				command = commandline
				args = []
			else:
				command, args = commandline.split(" ", 1)
				args = [a for a in args.split(" ") if len(a) > 0]
			if command[0] != '_':
				cmd = Commands.commands.get(command.lower(), None)
				if not cmd.__doc__ or cmd.__doc__.find("admin") == -1 or Irc.is_admin(source):
					if cmd:
						req = Request(instance, reply, source, commandline)
						t = threading.Thread(target = run_command, args = (cmd, req, args))
						t.start()
hooks["PRIVMSG"] = message

def join(instance, source, channel, account, _):
	if account == "*":
		account = False
	nick = Irc.get_nickname(source)
	with Global.account_lock:
		if nick  == instance:
			Global.account_cache[channel] = {}
		Global.account_cache[channel][nick] = account
		for channel in Global.account_cache:
			if nick in Global.account_cache[channel]:
				Global.account_cache[channel][nick] = account
				Logger.log("w", "Propagating %s=%s into %s" % (nick, account, channel))
hooks["JOIN"] = join

def part(instance, source, channel, *_):
	nick = Irc.get_nickname(source)
	with Global.account_lock:
		if nick == instance:
			del Global.account_cache[channel]
			Logger.log("w", "Removing cache for " + channel)
			return
		if nick in Global.account_cache[channel]:
			del Global.account_cache[channel][nick]
			Logger.log("w", "Removing %s from %s" % (nick, channel))
hooks["PART"] = part

def kick(instance, _, channel, nick, *__):
	with Global.account_lock:
		if nick == instance:
			del Global.account_cache[channel]
			Logger.log("w", "Removing cache for " + channel)
			return
		if nick in Global.account_cache[channel]:
			del Global.account_cache[channel][nick]
			Logger.log("w", "Removing %s from %s" % (nick, channel))
hooks["KICK"] = kick

def quit(instance, source, _):
	nick = Irc.get_nickname(source)
	with Global.account_lock:
		if nick == instance:
			chans = []
			for channel in Global.account_cache:
				if nick in Global.account_cache[channel]:
					chans.append(channel)
			for channel in chans:
					del Global.account_cache[channel]
					Logger.log("w", "Removing cache for " + channel)
			return
		for channel in Global.account_cache:
			if nick in Global.account_cache[channel]:
				del Global.account_cache[channel][nick]
				Logger.log("w", "Removing %s from %s" % (nick, channel))
hooks["QUIT"] = quit

def account(instance, source, account):
	if account == "*":
		account = False
	nick = Irc.get_nickname(source)
	with Global.account_lock:
		for channel in Global.account_cache:
			if nick in Global.account_cache[channel]:
				Global.account_cache[channel][nick] = account
				Logger.log("w", "Propagating %s=%s into %s" % (nick, account, channel))
hooks["ACCOUNT"] = account

def _nick(instance, source, newnick):
	nick = Irc.get_nickname(source)
	with Global.account_lock:
		for channel in Global.account_cache:
			if nick in Global.account_cache[channel]:
				Global.account_cache[channel][newnick] = Global.account_cache[channel][nick]
				Logger.log("w", "%s -> %s in %s" % (nick, newnick, channel))
				del Global.account_cache[channel][nick]
hooks["NICK"] = _nick

def names(instance, _, __, eq, channel, names):
	names = names.split(" ")
	with Global.account_lock:
		for n in names:
			n = Irc.strip_nickname(n)
			Global.account_cache[channel][n] = None
hooks["353"] = names

def error(instance, *_):
	Logger.log("ce", instance + " disconnected")
	raise socket.error()
hooks["ERROR"] = error

def whois_host(instance, _, __, target, *___):
	Global.instances[instance].lastwhois = False
hooks["311"] = whois_host

def whois_ident(instance, _, __, target, account, ___):
	Global.instances[instance].lastwhois = account
hooks["330"] = whois_ident

def whois_end(instance, _, __, target, ___):
	try:
		nick, q = Global.instances[instance].whois_queue.get(False)
		if Irc.equal_nicks(target, nick):
			Logger.log("w", instance + ": WHOIS of " + target + " is " + repr(Global.instances[instance].lastwhois))
			q.put(Global.instances[instance].lastwhois, True)
		else:
			Logger.log("we", instance + ": WHOIS reply for " + target + " but queued " + nick + " returning None")
			q.put(None, True)
		Global.instances[instance].lastwhois = None
		Global.instances[instance].whois_queue.task_done()
	except Queue.Empty:
		Logger.log("we", instance + ": WHOIS reply for " + target + " but nothing queued")
hooks["318"] = whois_end

def cap(instance, _, __, ___, caps):
	if caps.rstrip(" ") == "sasl":
		Irc.instance_send(instance, ("AUTHENTICATE", "PLAIN"), lock = False)
hooks["CAP"] = cap

def authenticate(instance, _, data):
	if data == "+":
		load = Config.config["account"] + "\0" + Config.config["account"] + "\0" + Config.config["password"]
		Irc.instance_send(instance, ("AUTHENTICATE", load.encode("base64").rstrip("\n")), lock = False)
hooks["AUTHENTICATE"] = authenticate

def sasl_success(instance, _, data, __):
	Logger.log("c", "Finished authentication")
	Irc.instance_send(instance, ("CAP", "END"), lock = False)
	Irc.instance_send(instance, ("CAP", "REQ", "extended-join account-notify"), lock = False)
hooks["903"] = sasl_success
