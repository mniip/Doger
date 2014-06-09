# coding=utf8
import sys, os
import Irc, Transactions, Logger, Global

commands = {}

def ping(req, _):
	"""%ping - Pong"""
	req.reply("Pong")
commands["ping"] = ping

def balance(req, _):
	"""%balance - Displays your confirmed and unconfirmed balance"""
	acct = Irc.account(req.serv, req.nick)
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	confirmed = int(Transactions.balance(acct))
	full = int(Transactions.balance(acct, 0))
	if full == confirmed:
		req.reply("Your balance is Ɖ%i" % (confirmed))
	else:
		req.reply("Your balance is Ɖ%i (+Ɖ%i unconfirmed)" % (confirmed, full - confirmed))
commands["balance"] = balance

def deposit(req, _):
	"""%deposit - Displays your deposit address"""
	acct = Irc.account(req.serv, req.nick)
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	req.reply("To deposit, send coins to %s (transactions will be credited after 4 confirmations)" % Transactions.deposit_address(acct).encode("utf8"))
commands["deposit"] = deposit

def withdraw(req, arg):
	"""%withdraw <address> [amount] - Sends 'amount' coins to the specified dogecoin address. If no amount specified, send the whole balance"""
	if len(arg) == 0:
		return req.reply("%withdraw <address> [amount]")
	acct = Irc.account(req.serv, req.nick)
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	with Transactions.get_lock():
		balance = int(Transactions.balance(acct))
		if balance:
			if len(arg) == 1:
				amount = balance - 1
				print(amount)
			else:
				try:
					amount = int(arg[1])
					if amount <= 0:
						raise ValueError()
				except ValueError as e:
					req.reply_private(repr(arg[1]) + " - invalid amount")
					return None
			to = arg[0]
			if amount > balance - 1:
				return req.reply_private("You tried to withdraw Ɖ%i (Ɖ+1 fee) but you only have Ɖ%i" % (amount, balance))
			if not Transactions.verify_address(to):
				return req.reply_private(to + " doesn't seem to be a valid dogecoin address")
			id = Logger.get_id()
			Logger.log(id, "moving %d(+1) from acct:%s(%d) to %s" % (amount, acct, balance, to))
			tx = Transactions.withdraw(acct, to, amount)
			if tx:
				Logger.log(id, "success, TX id is %s (acct:%s(%d))" % (tx.encode("utf8"), acct, Transactions.balance(acct)))
				req.reply("Coins have been sent, see http://dogechain.info/tx/%s [%s]" % (tx.encode("utf8"), id))
			else:
				Logger.log(id, "failed (acct:%s(%d))" % (acct, Transactions.balance(acct)))
				req.reply("Something went wrong, report this to mniip [%s]" % (id))
		else:
			return req.reply_private("You don't have any coins on your account")
commands["withdraw"] = withdraw

def tip(req, arg):
	"""%tip <target> <amount> - Sends 'amount' coins to the specified nickname"""
	if len(arg) < 2:
		return req.reply("%tip <target> <amount>")
	acct = Irc.account(req.serv, req.nick)
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	with Transactions.get_lock():
		balance = Transactions.balance(acct)
		if balance:
			try:
				amount = int(arg[1])
				if amount <= 0:
					raise ValueError()
			except ValueError as e:
				req.reply_private(repr(arg[1]) + " - invalid amount")
				return None
			to = arg[0]
			toacct = Irc.account(req.serv, to)
			if not toacct:
				return req.reply_private(to + " is not online or not identified with freenode services")
			if toacct[-4:] == "SERV":
				return req.reply("Services don't accept doge")
			if amount > balance:
				return req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (amount, balance))
			id = Logger.get_id()
			Logger.log(id, "moving %d from acct:%s(%d) to acct:%s(%d)" % (amount, acct, balance, toacct, Transactions.balance(toacct)))
			if Transactions.tip(acct, toacct, amount):
				Logger.log(id, "success (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
				if Irc.toupper(req.nick) == Irc.toupper(req.target):
					req.reply("Done [%s]" % (id))
				else:
					req.say("Such %s tipped much Ɖ%i to %s! (to claim /msg Doger help) [%s]" % (req.nick, amount, to, id))
				req.serv.send("PRIVMSG", to, "Such %s has tipped you Ɖ%i (to claim /msg Doger help) [%s]" % (req.nick, amount, id))
				return
			else:
				Logger.log(id, "failed (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
				req.reply("Something went wrong, report this to mniip [%s]" % (id))
		else:
			req.reply_private("You don't have any coins on your account")
commands["tip"] = tip

def mtip(req, arg):
	"""%mtip <targ1> <amt1> [<targ2> <amt2> ...] - Send multiple tips at once"""
	if not len(arg) or len(arg) % 2:
		return req.reply("%mtip <targ1> <amt1> [<targ2> <amt2> ...]")
	acct = Irc.account(req.serv, req.nick)
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	with Transactions.get_lock():
		balance = Transactions.balance(acct)
		for i in range(0, len(arg), 2):
			try:
				a = int(arg[i + 1])
				if a <= 0:
					raise ValueError()
			except ValueError as e:
				req.reply_private(repr(arg[i + 1]) + " - invalid amount")
				return None
		tips = {}
		totip = 0
		for i in range(0, len(arg), 2):
			found = False
			for nick in tips:
				if Irc.toupper(nick) == Irc.toupper(arg[i]):
					tips[nick] += int(arg[i + 1])
					totip += int(arg[i + 1])
					found = True
					break
			if not found:
				tips[arg[i]] = int(arg[i + 1])
				totip += int(arg[i + 1])
		if totip > balance:
			return req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (amount, balance))
		tipped = []
		failed = []
		for to in tips:
			amt = tips[to]
			toacct = Irc.account(req.serv, to)
			if toacct:
				id = Logger.get_id()
				Logger.log(id, "moving %d from acct:%s(%d) to acct:%s(%d)" % (amt, acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
				if Transactions.tip(acct, Irc.toupper(to), amt):
					Logger.log(id, "success (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
					tipped.append((to, amt, id))
				else:
					Logger.log(id, "failed (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
					failed.append((to, amt, id))
					failed += " %s %d [%s]" % (to, amt, id)
		output = ""
		if len(tipped):
			output += "Tipped:"
			for to, amt, id in tipped:
				output += " %s %d [%s]" % (to, amt, id)
		if len(failed):
			output += "  Failed:"
			for to, amt, id in failed:
				output += " %s %d [%s]" % (to, amt, id)
		req.reply(output)
commands["mtip"] = mtip

def donate(req, arg):
	"""%donate <amount> - Donates 'amount' coins to the developers of this bot"""
	if len(arg) < 1:
		return req.reply("%donate <amount>")
	acct = Irc.account(req.serv, req.nick)
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	with Transactions.get_lock():
		balance = Transactions.balance(acct)
		if balance:
			try:
				amount = int(arg[0])
				if amount <= 0:
					raise ValueError()
			except ValueError as e:
				req.reply_private(repr(arg[0]) + " - invalid amount")
				return None
			toacct = "@DONATIONS"
			if amount > balance:
				return req.reply_private("You tried to donate Ɖ%i but you only have Ɖ%i" % (amount, balance))
			id = Logger.get_id()
			Logger.log(id, "moving %d from acct:%s(%d) to acct:%s(%d)" % (amount, acct, balance, toacct, Transactions.balance(toacct)))
			if Transactions.tip(acct, toacct, amount):
				Logger.log(id, "success (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
				req.reply("Done [%s]" % (id))
				return
			else:
				Logger.log(id, "failed (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
				req.reply("Something went wrong, report this to mniip [%s]" % (id))
		else:
			req.reply_private("You don't have any coins on your account")
commands["donate"] = donate

def _help(req, arg):
	"""%help - list of commands; %help <command> - help for specific command"""
	if len(arg):
		if arg[0][0] == '%':
			name = arg[0][1:]
		else:
			name = arg[0]
		cmd = commands.get(name, None)
		if cmd:
			req.reply(cmd.__doc__.split("\n")[0])
	else:
		req.reply("A fido replacement bot by mniip. Commands: %tip %balance %withdraw %deposit %mtip %donate %help   Try: %help <command>")
commands["help"] = _help

def load(req, arg):
	"""
	admin"""
	for mod in arg:
		reload(sys.modules[mod])
	req.reply("Done")
commands["reload"] = load

def _exec(req, arg):
	"""
	admin"""
	try:
		req.reply(repr(eval(" ".join(arg))))
	except SyntaxError:
		exec(" ".join(arg))
commands["exec"] = _exec

def die(req, arg):
	"""
	admin"""
	if arg[0] == "all":
		with Transactions.get_lock():
			Global.lock.release()
	elif arg[0] == "exec":
		for instance in Global.connections:
			conn = Global.connections[instance]
			if conn:
				conn.disconnect()
		os.execl(sys.executable, *([sys.executable] + sys.argv))
	elif arg[0] == "thread":
		req.serv.running = 0
commands["die"] = die

def ignore(req, arg):
	"""
	admin"""
	req.serv.ignore(arg[0], int(arg[1]))
commands["ignore"] = ignore
