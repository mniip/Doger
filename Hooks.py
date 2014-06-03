# coding=utf8
import traceback, sys, re

import Irc, Transactions, Commands

hooks = {}

def end_of_motd(serv, *_):
	for channel in serv.config["autojoin"]:
		serv.send("JOIN", channel)
hooks["376"] = end_of_motd

def ping(serv, *_):
	serv.send("PONG")
hooks["PING"] = ping

class Request():
	pass

def message(serv, source, target, text):
	if text[0] == '%' or target == serv.nick:
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
			if not cmd.__doc__ or cmd.__doc__.find("admin") == -1 or src == "mniip":
				if cmd:
					try:
						request = Request()
						request.serv = serv
						request.reply = reply
						request.source = source
						ret = cmd(request, args)
					except Exception as e:
						type, value, tb = sys.exc_info()
						traceback.print_tb(tb)
						ret = repr(e)
					if isinstance(ret, str):
						ret = ret.translate(None, "\r\n\a\b\x00")
						if not len(ret):
							ret = "[I have nothing to say]"
						serv.send("PRIVMSG", reply, src + ": " + ret)
	elif source.split("@")[1] == "lucas.fido.pw":
		m = re.match(r"Wow!  (\S*) just sent you Ð\d*\.", text)
		if not m:
			m = re.match(r"Wow!  (\S*) sent Ð\d* to Doger!", text)
		if m:
			nick = m.group(1)
			address = Transactions.deposit_address(Irc.toupper(nick))
			serv.send("PRIVMSG", "fido", "withdraw " + address.encode("utf8"))
			serv.send("PRIVMSG", nick, "Your tip has been withdrawn to your account and will appear in %balance soon")
hooks["PRIVMSG"] = message
