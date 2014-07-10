# coding=utf8
import sys, os, time
import Irc, Transactions, Logger, Global, Hooks, Config

commands = {}

def ping(req, _):
	"""%ping - Pong"""
	req.reply("Pong")
commands["ping"] = ping

def test(req, arg):
	req.reply(repr(Irc.account_names(arg)))
commands["test"] = test

def balance(req, _):
	"""%balance - Displays your confirmed and unconfirmed balance"""
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	confirmed = Transactions.balance(acct)
	pending = Transactions.balance_unconfirmed(acct)
	if pending:
		req.reply("Your balance is Ɖ%i (+Ɖ%i unconfirmed)" % (confirmed, pending))
	else:
		req.reply("Your balance is Ɖ%i" % (confirmed))
commands["balance"] = balance

def deposit(req, _):
	"""%deposit - Displays your deposit address"""
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	req.reply("To deposit, send coins to %s (transactions will be credited after %d confirmations)" % (Transactions.deposit_address(acct), Config.config["confirmations"]))
commands["deposit"] = deposit

def withdraw(req, arg):
	"""%withdraw <address> [amount] - Sends 'amount' coins to the specified dogecoin address. If no amount specified, sends the whole balance"""
	if len(arg) == 0:
		return req.reply(gethelp("withdraw"))
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	if len(arg) == 1:
		amount = max(Transactions.balance(acct) - 1, 1)
	else:
		try:
			amount = int(arg[1])
			if amount <= 0:
				raise ValueError()
			amount = min(amount, 1000000000000)
		except ValueError as e:
			req.reply_private(repr(arg[1]) + " - invalid amount")
			return None
	to = arg[0]
	if not Transactions.verify_address(to):
		return req.reply_private(to + " doesn't seem to be a valid dogecoin address")
	with Logger.token() as token:
		try:
			tx = Transactions.withdraw(acct, to, amount)
			token.log("t", "acct:%s withdrew %d, TX id is %s (acct:%s(%d))" % (acct, amount, tx, acct, Transactions.balance(acct)))
			req.reply("Coins have been sent, see http://dogechain.info/tx/%s [%s]" % (tx, token.id))
		except Transactions.NotEnoughMoney:
			req.reply_private("You tried to withdraw Ɖ%i (+Ɖ1 TX fee) but you only have Ɖ%i" % (amount, Transactions.balance(acct)))
		except Transactions.InsufficientFunds:
			token.log("te", "acct:%s tried to withdraw %d" % (acct, amount))
			req.reply("Something went wrong, report this to mniip [%s]" % (token.id))
commands["withdraw"] = withdraw

def tip(req, arg):
	"""%tip <target> <amount> - Sends 'amount' coins to the specified nickname"""
	if len(arg) < 2:
		return req.reply(gethelp("tip"))
	to = arg[0]
	acct, toacct = Irc.account_names([req.nick, to])
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	if not toacct:
		if toacct == None:
			return req.reply_private(to + " is not online")
		else:
			return req.reply_private(to + " is not identified with freenode services")
	try:
		amount = int(arg[1])
		if amount <= 0:
			raise ValueError()
		amount = min(amount, 1000000000000)
	except ValueError as e:
		req.reply_private(repr(arg[1]) + " - invalid amount")
		return None
	with Logger.token() as token:
		try:
			Transactions.tip(acct, toacct, amount)
			token.log("t", "acct:%s tipped %d to acct:%s(%d)" % (acct, amount, toacct, Transactions.balance(toacct)))
			if Irc.equal_nicks(req.nick, req.target):
				req.reply("Done [%s]" % (token.id))
			else:
				req.say("Such %s tipped much Ɖ%i to %s! (to claim /msg Doger help) [%s]" % (req.nick, amount, to, token.id))
			Irc.instance_send(req.instance, "PRIVMSG", to, "Such %s has tipped you Ɖ%i (to claim /msg Doger help) [%s]" % (req.nick, amount, token.id))
		except Transactions.NotEnoughMoney:
			req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (amount, Transactions.balance(acct)))
commands["tip"] = tip

def mtip(req, arg):
	"""%mtip <targ1> <amt1> [<targ2> <amt2> ...] - Send multiple tips at once"""
	if not len(arg) or len(arg) % 2:
		return req.reply(gethelp("mtip"))
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	for i in range(0, len(arg), 2):
		try:
			if int(arg[i + 1]) <= 0:
				raise ValueError()
		except ValueError as e:
			req.reply_private(repr(arg[i + 1]) + " - invalid amount")
			return None
	targets = []
	amounts = []
	total = 0
	for i in range(0, len(arg), 2):
		target = arg[i]
		amount = int(arg[i + 1])
		amount = min(amount, 1000000000000)
		found = False
		for i in range(len(targets)):
			if Irc.equal_nicks(targets[i], target):
				amounts[i] += amount
				total += amount
				found = True
				break
		if not found:
			targets.append(target)
			amounts.append(amount)
			total += amount
	balance = Transactions.balance(acct)
	if total > balance:
		return req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (total, balance))
	accounts = Irc.account_names(targets)
	totip = {}
	failed = ""
	tipped = ""
	for i in range(len(targets)):
		if accounts[i]:
			totip[accounts[i]] = amounts[i]
			tipped += " %s %d" % (targets[i], amounts[i])
		elif accounts[i] == None:
			failed += " %s (offline)" % (targets[i])
		else:
			failed += " %s (unidentified)" % (targets[i])
	with Logger.token() as token:
		try:
			Transactions.tip_multiple(acct, totip)
			token.log("t", "acct:%s mtipped: %s" % (acct, repr(totip)))
			tipped += " [%s]" % (token.id)
		except Transactions.NotEnoughMoney:
			return req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (total, Transactions.balance(acct)))
	output = "Tipped:" + tipped
	if len(failed):
		output += "  Failed:" + failed
	req.reply(output)
commands["mtip"] = mtip

def donate(req, arg):
	if len(arg) < 1:
		return req.reply(gethelp("donate"))
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	toacct = "@DONATIONS"
	try:
		amount = int(arg[0])
		if amount <= 0:
			raise ValueError()
		amount = min(amount, 1000000000000)
	except ValueError as e:
		req.reply_private(repr(arg[0]) + " - invalid amount")
		return None
	with Logger.token() as token:
		try:
			Transactions.tip(acct, toacct, amount)
			token.log("t", "acct:%s tipped %d to acct:%s(%d)" % (acct, amount, toacct, Transactions.balance(toacct)))
			req.reply("Done [%s]" % (token.id))
		except Transactions.NotEnoughMoney:
			req.reply_private("You tried to donate Ɖ%i but you only have Ɖ%i" % (amount, Transactions.balance(acct)))
commands["donate"] = donate

def gethelp(name):
	if name[0] == Config.config["prefix"]:
		name = name[1:]
	cmd = commands.get(name, None)
	if cmd and cmd.__doc__:
		return cmd.__doc__.split("\n")[0].replace("%", Config.config["prefix"])

def _help(req, arg):
	"""%help - list of commands; %help <command> - help for specific command"""
	if len(arg):
		h = gethelp(arg[0])
		if h:
			req.reply(h)
	else:
		if not Irc.equal_nicks(req.target, req.nick):
			return req.reply("I'm Doger, an IRC dogecoin tipbot. For more info do /msg Doger help")
		acct = Irc.account_names([req.nick])[0]
		if acct:
			ident = "you're identified as \2" + acct + "\2"
		else:
			ident = "you're not identified"
		req.say("I'm Doger, I'm an IRC dogecoin tipbot. To get help about a specific command, say \2%help <command>\2  Commands: %tip %balance %withdraw %deposit %mtip %donate %help".replace("%", Config.config["prefix"]))
		req.say("Note that to receive or send tips you should be identified with freenode services (%s). For any support questions, including those related to lost coins, join ##doger" % (ident))
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
	exec(" ".join(arg).replace("$", "\n"))
commands["exec"] = _exec

def ignore(req, arg):
	"""
	admin"""
	Irc.ignore(arg[0], int(arg[1]))
commands["ignore"] = ignore

def die(req, arg):
	"""
	admin"""
	if arg[0] == "exec":
		for instance in Global.instances:
			Global.manager_queue.put(("Disconnect", instance))
		Global.manager_queue.join()
		Transactions.stop()
		os.execv(sys.executable, [sys.executable] + sys.argv)
	elif arg[0] == "thread":
		Global.manager_queue.put(("Reconnect", req.instance))
	else:
		for instance in Global.instances:
			Global.manager_queue.put(("Disconnect", instance))
		Global.manager_queue.join()
		Transactions.stop()
		Global.manager_queue.put(("Die",))
commands["die"] = die

def _as(req, arg):
	"""
	admin"""
	_, target, text = req.text.split(" ", 2)
	if target[0] == '@':
		Global.account_cache[""] = {"@": target[1:]}
		target = "@"
	if text.find(" ") == -1:
		command = text
		args = []
	else:
		command, args = text.split(" ", 1)
		args = [a for a in args.split(" ") if len(a) > 0]
	if command[0] != '_':
		cmd = commands.get(command.lower(), None)
		if not cmd.__doc__ or cmd.__doc__.find("admin") == -1 or Irc.is_admin(source):
			if cmd:
				req = Hooks.FakeRequest(req, target, text)
				Hooks.run_command(cmd, req, args)
commands["as"] = _as
