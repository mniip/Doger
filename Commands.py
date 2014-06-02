# coding=utf8
import sys
import Irc, Transactions, Logger

def ping(*_):
	return "Pong"

def acc(serv, reply, src, who, *_):
	return repr(Irc.account(serv, who))

def balance(serv, reply, src, *_):
	acct = Irc.toupper(Irc.get_nickname(src))
	confirmed = int(Transactions.balance(acct))
	full = int(Transactions.balance(acct, 0))
	if full == confirmed:
		return "Your balance is %iƉ" % (confirmed)
	else:
		return "Your balance is %iƉ (+%iƉ unconfirmed)" % (confirmed, full - confirmed)

def deposit(serv, reply, src, *_):
	acct = Irc.toupper(Irc.get_nickname(src))
	return "To deposit, send coins to %s (transactions will be credited after 4 confirmations)" % Transactions.deposit_address(acct).encode("utf8")

def withdraw(serv, reply, src, *arg):
	if len(arg) == 0:
		return "%withdraw <address> [amount]"
	acct = Irc.toupper(Irc.get_nickname(src))
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
				return arg[1] + " - invalid amount"
		to = arg[0]
		if amount > balance - 1:
			return "You tried to withdraw %iƉ (+1Ɖ fee) but you only have %iƉ" % (amount, balance)
		if not Transactions.verify_address(to):
			return to + " doesn't seem to be a valid dogecoin address"
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
		return "You don't have any coins on your account"

def tip(serv, reply, src, *arg):
	if len(arg) < 2:
		return "%tip <target> <amount>"
	acct = Irc.toupper(Irc.get_nickname(src))
	balance = Transactions.balance(acct)
	if balance:
		try:
			amount = int(arg[1])
			if amount <= 0:
				raise ValueError()
		except ValueError as e:
			return arg[1] + " - invalid amount"
		to = arg[0]
		toacct = Irc.toupper(to)
		if toacct[-4:] == "SERV":
			return "Services don't accept doge"
		if not len(to)or not Irc.anyone(serv, to):
			return to + " is not online"
		if amount > balance:
			return "You tried to tip %iƉ but you only have %iƉ" % (amount, balance)
		id = Logger.get_id()
		Logger.log(id, "moving %d from acct:%s(%d) to acct:%s(%d)" % (amount, acct, balance, toacct, Transactions.balance(toacct)))
		if Transactions.tip(acct, toacct, amount):
			Logger.log(id, "success (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
			if Irc.toupper(Irc.get_nickname(src)) == Irc.toupper(reply):
				serv.send("PRIVMSG", reply, "Done [%s]" % (id))
			else:
				serv.send("PRIVMSG", reply, "Such %s tipped much %iƉ to %s! (to claim /msg Doger %%help) [%s]" % (Irc.get_nickname(src), amount, to, id))
			serv.send("PRIVMSG", to, "Such %s has tipped you %iƉ (to claim /msg Doger %%help) [%s]" % (Irc.get_nickname(src), amount, id))
			return None
		else:
			Logger.log(id, "failed (acct:%s(%d) acct:%s(%d))" % (acct, Transactions.balance(acct), toacct, Transactions.balance(toacct)))
			return "Something went wrong, report this to mniip"
	else:
		return "You don't have any coins on your account"

def mtip(serv, reply, src, *arg):
	if not len(arg) or len(arg) % 2:
		return "%mtip <targ1> <amt1> [<targ2> <amt2> ...]"
	acct = Irc.toupper(Irc.get_nickname(src))
	balance = Transactions.balance(acct)
	for i in range(0, len(arg), 2):
		try:
			a = int(arg[i + 1])
			if a <= 0:
				raise ValueError()
		except ValueError as e:
			return arg[i + 1] + " - invalid amount"
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
		if not found and Irc.anyone(serv, arg[i]):
			tips[arg[i]] = int(arg[i + 1])
			totip += int(arg[i + 1])
	if totip > balance:
		return "You tried to tip %iƉ but you only have %iƉ" % (amount, balance)
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

def help(serv, reply, src, *_):
	return "Balance: %balance   To deposit: %deposit   To withdraw: %withdraw <address> [amount]   To tip: %tip <target> <amount>"

def load(serv, reply, src, module, *_):
	"""sudo"""
	reload(sys.modules[module])
	return "Done"

def run(serv, reply, src, *args):
	"""sudo"""
	return repr(eval(" ".join(args)))
