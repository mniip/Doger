# coding=utf8
import sys
import Irc, Transactions, Logger

commands = {}

def ping(req, _):
	"""%ping - Pong"""
	return "Pong"
commands["ping"] = ping

def balance(req, _):
	"""%balance - Displays your confirmed and unconfirmed balance"""
	acct = Irc.toupper(Irc.get_nickname(req.source))
	confirmed = int(Transactions.balance(acct))
	full = int(Transactions.balance(acct, 0))
	if full == confirmed:
		return "Your balance is %iƉ" % (confirmed)
	else:
		return "Your balance is %iƉ (+%iƉ unconfirmed)" % (confirmed, full - confirmed)
commands["balance"] = balance

def deposit(req, _):
	"""%deposit - Displays your deposit address"""
	acct = Irc.toupper(Irc.get_nickname(req.source))
	return "To deposit, send coins to %s (transactions will be credited after 4 confirmations)" % Transactions.deposit_address(acct).encode("utf8")
commands["deposit"] = deposit

def withdraw(req, arg):
	"""%withdraw <address> [amount] - Sends 'amount' coins to the specified dogecoin address. If no amount specified, send the whole balance"""
	if len(arg) == 0:
		return "%withdraw <address> [amount]"
	acct = Irc.toupper(Irc.get_nickname(req.source))
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
					req.serv.send("PRIVMSG", Irc.get_nickname(req.source), repr(arg[1]) + " - invalid amount")
					return None
			to = arg[0]
			if amount > balance - 1:
				req.serv.send("PRIVMSG", Irc.get_nickname(req.source), "You tried to withdraw %iƉ (+1Ɖ fee) but you only have %iƉ" % (amount, balance))
				return None
			if not Transactions.verify_address(to):
				req.serv.send("PRIVMSG", Irc.get_nickname(req.source), to + " doesn't seem to be a valid dogecoin address")
				return None
			id = Logger.get_id()
			Logger.log(id, "moving %d(+1) from acct:%s(%d) to %s" % (amount, acct, balance, to))
			tx = Transactions.withdraw(acct, to, amount)
			if tx:
				Logger.log(id, "success, TX id is %s (acct:%s(%d))" % (tx.encode("utf8"), acct, Transactions.balance(acct)))
				return "Coins have been sent, see http://dogechain.info/tx/%s [%s]" % (tx.encode("utf8"), id)
			else:
				Logger.log(id, "failed (acct:%s(%d))" % (acct, Transactions.balance(acct)))
				return "Something went wrong, report this to mniip"
		else:
			req.serv.send("PRIVMSG", Irc.get_nickname(req.source), "You don't have any coins on your account")
			return None
commands["withdraw"] = withdraw

def tip(req, arg):
	"""%tip <target> <amount> - Sends 'amount' coins to the specified nickname"""
	if len(arg) < 2:
		return "%tip <target> <amount>"
	acct = Irc.toupper(Irc.get_nickname(req.source))
	with Transactions.get_lock():
		balance = Transactions.balance(acct)
		if balance:
			try:
				amount = int(arg[1])
				if amount <= 0:
					raise ValueError()
			except ValueError as e:
				req.serv.send("PRIVMSG", Irc.get_nickname(req.source), repr(arg[1]) + " - invalid amount")
				return None
			to = arg[0]
			toacct = Irc.toupper(to)
			if toacct[-4:] == "SERV":
				return "Services don't accept doge"
			if not len(to)or not Irc.anyone(req.serv, to):
				req.serv.send("PRIVMSG", Irc.get_nickname(req.source), to + " is not online")
				return None
			if amount > balance:
				req.serv.send("PRIVMSG", Irc.get_nickname(req.source), "You tried to tip %iƉ but you only have %iƉ" % (amount, balance))
				return None
			id = Logger.get_id()
			Logger.log(id, "moving %d from acct:%s(%d) to acct:%s(%d)" % (amount, acct, balance, toacct, Transactions.balance(toacct)))
			if Transactions.tip(acct, toacct, amount):
				Logger.log(id, "success (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
				if Irc.toupper(Irc.get_nickname(req.source)) == Irc.toupper(req.reply):
					req.serv.send("PRIVMSG", req.reply, "Done [%s]" % (id))
				else:
					req.serv.send("PRIVMSG", req.reply, "Such %s tipped much %iƉ to %s! (to claim /msg Doger help) [%s]" % (Irc.get_nickname(req.source), amount, to, id))
				req.serv.send("PRIVMSG", to, "Such %s has tipped you %iƉ (to claim /msg Doger help) [%s]" % (Irc.get_nickname(req.source), amount, id))
				return None
			else:
				Logger.log(id, "failed (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
				return "Something went wrong, report this to mniip"
		else:
			req.serv.send("PRIVMSG", Irc.get_nickname(req.source), "You don't have any coins on your account")
			return None
commands["tip"] = tip

def mtip(req, arg):
	"""%mtip <targ1> <amt1> [<targ2> <amt2> ...] - Send multiple tips at once"""
	if not len(arg) or len(arg) % 2:
		return "%mtip <targ1> <amt1> [<targ2> <amt2> ...]"
	acct = Irc.toupper(Irc.get_nickname(req.source))
	with Transactions.get_lock():
		balance = Transactions.balance(acct)
		for i in range(0, len(arg), 2):
			try:
				a = int(arg[i + 1])
				if a <= 0:
					raise ValueError()
			except ValueError as e:
				req.serv.send("PRIVMSG", Irc.get_nickname(req.source), repr(arg[i + 1]) + " - invalid amount")
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
			if not found and Irc.anyone(req.serv, arg[i]):
				tips[arg[i]] = int(arg[i + 1])
				totip += int(arg[i + 1])
		if totip > balance:
			req.serv.send("PRIVMSG", Irc.get_nickname(req.source), "You tried to tip %iƉ but you only have %iƉ" % (amount, balance))
			return None
		tipped = []
		failed = []
		for to in tips:
			amt = tips[to]
			toacct = Irc.toupper(to)
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
		return output
commands["mtip"] = mtip

def _help(req, arg):
	"""%help - list of commands; %help <command> - help for specific command"""
	if len(arg):
		if arg[0][0] == '%':
			name = arg[0][1:]
		else:
			name = arg[0]
		cmd = commands.get(name, None)
		if cmd:
			return cmd.__doc__.split("\n")[0]
	else:
		return "A fido replacement bot by mniip. Commands: %tip %balance %withdraw %deposit %mtip %help   Try: %help <command>"
commands["help"] = _help

def load(req, arg):
	"""
	admin"""
	for mod in arg:
		reload(sys.modules[mod])
	return "Done"
commands["reload"] = load

def _exec(req, arg):
	"""
	admin"""
	try:
		return repr(eval(" ".join(arg)))
	except SyntaxError:
		exec(" ".join(arg))
commands["exec"] = _exec

def die(req, arg):
	"""
	admin"""
	req.serv.running = False
commands["die"] = die

def ignore(req, arg):
	"""
	admin"""
	req.serv.ignore(arg[0], int(arg[1]))
commands["ignore"] = ignore
