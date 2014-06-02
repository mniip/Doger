import Irc, Commands

def numeric_376(serv, *_):
	for channel in serv.autojoin:
		serv.send("JOIN", channel)

def PING(serv, *_):
	serv.send("PONG")

def PRIVMSG(serv, source, target, text):
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
			cmd = getattr(Commands, command, None)
			if cmd:
				try:
					ret = cmd(serv, reply, source, *args)
				except Exception as e:
					ret = repr(e)
				if isinstance(ret, str):
					ret = ret.translate(None, "\r\n\a\b\x00")
					if not len(ret):
						ret = "[I have nothing to say]"
					serv.send("PRIVMSG", reply, src + ": " + ret)
