# coding=utf8
import Irc, Transactions

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
	balance = Transactions.balance(acct)
	if balance:
		if len(arg) == 1:
			amount = balance - 1
			print(amount)
		else:
			try:
				amount = int(arg[1])-1
				if amount <= 0:
					raise ValueError()
			except ValueError as e:
				return arg[1] + " - invalid amount"
		to = arg[0]
		if amount > balance - 1:
			return "You tried to withdraw %iƉ (+1Ɖ fee) but you only have %iƉ" % (amount, balance)
		tx = Transactions.withdraw(acct, to, amount)
		if tx:
			return "Coins have been sent, see http://dogechain.info/tx/%s" % (tx.encode("utf8"))
		else:
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
		if Irc.toupper(to)[-4:] == "SERV":
			return "Services don't accept doge"
		if not len(to)or not Irc.anyone(serv, to):
			return to + " is not online"
		if amount > balance:
			return "You tried to tip %iƉ but you only have %iƉ" % (amount, balance)
		if Transactions.tip(acct, Irc.toupper(to), amount):
			if Irc.toupper(Irc.get_nickname(src)) != Irc.toupper(reply):
				serv.send("PRIVMSG", reply, "Such %s tipped much %iƉ to %s! (to claim /msg Doger %%help)" % (Irc.get_nickname(src), amount, to))
			serv.send("PRIVMSG", to, "Such %s has tipped you %iƉ (to claim /msg Doger %%help)" % (Irc.get_nickname(src), amount))
			return None
		else:
			return "Something went wrong, report this to mniip"
	else:
		return "You don't have any coins on your account"

def help(serv, reply, src, *_):
	return "Balance: %balance   To deposit: %deposit   To withdraw: %withdraw <address> [amount]   To tip: %tip <target> <amount>"
