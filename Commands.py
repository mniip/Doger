# coding=utf8
import sys, os, time
import Irc, Transactions, Logger, Global, Hooks

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
	confirmed = int(Transactions.balance(acct))
	full = int(Transactions.balance(acct, 0))
	if full == confirmed:
		req.reply("Your balance is Ɖ%i" % (confirmed))
	else:
		req.reply("Your balance is Ɖ%i (+Ɖ%i unconfirmed)" % (confirmed, full - confirmed))
commands["balance"] = balance

def deposit(req, _):
	"""%deposit - Displays your deposit address"""
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	req.reply("To deposit, send coins to %s (transactions will be credited after 4 confirmations)" % Transactions.deposit_address(acct).encode("utf8"))
commands["deposit"] = deposit

def withdraw(req, arg):
	"""%withdraw <address> [amount] - Sends 'amount' coins to the specified dogecoin address. If no amount specified, sends the whole balance"""
	if len(arg) == 0:
		return req.reply("%withdraw <address> [amount]")
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	with Transactions.lock:
		balance = int(Transactions.balance(acct))
		if len(arg) == 1:
			amount = max(balance - 1, 0)
		else:
			try:
				amount = int(arg[1])
				if amount <= 0:
					raise ValueError()
			except ValueError as e:
				req.reply_private(repr(arg[1]) + " - invalid amount")
				return None
		to = arg[0]
		if amount > balance - 1 or balance == 1:
			return req.reply_private("You tried to withdraw Ɖ%i (Ɖ+1 TX fee) but you only have Ɖ%i" % (amount, balance))
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
commands["withdraw"] = withdraw

def tip(req, arg):
	"""%tip <target> <amount> - Sends 'amount' coins to the specified nickname"""
	if len(arg) < 2:
		return req.reply("%tip <target> <amount>")
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
	except ValueError as e:
		req.reply_private(repr(arg[1]) + " - invalid amount")
		return None
	with Transactions.lock:
		balance = Transactions.balance(acct)
		if amount > balance:
			return req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (amount, balance))
		id = Logger.get_id()
		Logger.log(id, "moving %d from acct:%s(%d) to acct:%s(%d)" % (amount, acct, balance, toacct, Transactions.balance(toacct)))
		if Transactions.tip(acct, toacct, amount):
			Logger.log(id, "success (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
			if Irc.equal_nicks(req.nick, req.target):
				req.reply("Done [%s]" % (id))
			else:
				req.say("Such %s tipped much Ɖ%i to %s! (to claim /msg Doger help) [%s]" % (req.nick, amount, to, id))
			Irc.instance_send(req.instance, "PRIVMSG", to, "Such %s has tipped you Ɖ%i (to claim /msg Doger help) [%s]" % (req.nick, amount, id))
			return
		else:
			Logger.log(id, "failed (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
			req.reply("Something went wrong, report this to mniip [%s]" % (id))
commands["tip"] = tip

def mtip(req, arg):
	"""%mtip <targ1> <amt1> [<targ2> <amt2> ...] - Send multiple tips at once"""
	if not len(arg) or len(arg) % 2:
		return req.reply("%mtip <targ1> <amt1> [<targ2> <amt2> ...]")
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
	accounts = Irc.account_names(targets)
	with Transactions.lock:
		balance = Transactions.balance(acct)
		if total > balance:
			return req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (amount, balance))
		tipped = ""
		failed = ""
		for i in range(len(targets)):
			if accounts[i]:
				id = Logger.get_id()
				Logger.log(id, "moving %d from acct:%s(%d) to acct:%s(%d)" % (amounts[i], acct, Transactions.balance(acct), accounts[i], Transactions.balance(accounts[i])))
				if Transactions.tip(acct, accounts[i], amounts[i]):
					Logger.log(id, "success (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), accounts[i], Transactions.balance(accounts[i])))
					tipped += " %s %d [%s]" % (targets[i], amounts[i], id)
				else:
					Logger.log(id, "failed (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), accounts[i], Transactions.balance(accounts[i])))
					tipped += " %s %d [%s]" % (targets[i], amounts[i], id)
			elif accounts[i] == None:
				failed += " %s (offline)" % (targets[i])
			else:
				failed += " %s (unidentified)" % (targets[i])
		output = "Tipped:" + tipped
		if len(failed):
			output += "  Failed:" + failed
		req.reply(output)
commands["mtip"] = mtip

def donate(req, arg):
	"""%donate <amount> - Donates 'amount' coins to the developers of this bot"""
	if len(arg) < 1:
		return req.reply("%donate <amount>")
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	with Transactions.lock:
		balance = Transactions.balance(acct)
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
		if not Irc.equal_nicks(req.target, req.nick):
			return req.reply("I'm Doger, an IRC dogecoin tipbot. For more info do /msg Doger help")
		acct = Irc.account_names([req.nick])[0]
		if acct:
			ident = "you're identified as \2" + acct + "\2"
		else:
			ident = "you're not identified"
		req.say("I'm Doger, I'm an IRC dogecoin tipbot. To get help about a specific command, say \2%help <command>\2  Commands: %tip %balance %withdraw %deposit %mtip %donate %help")
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
	try:
		req.reply(repr(eval(" ".join(arg))))
	except SyntaxError:
		exec(" ".join(arg))
commands["exec"] = _exec

def ignore(req, arg):
	"""
	admin"""
	Irc.ignore(arg[0], int(arg[1]))
commands["ignore"] = ignore

def die(req, arg):
	"""
	admin"""
	for instance in Global.instances:
		Global.manager_queue.put(("Disconnect", instance))
	Global.manager_queue.join()
	if arg[0] == "exec":
		os.execv(sys.executable, [sys.executable] + sys.argv)
	else:
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
