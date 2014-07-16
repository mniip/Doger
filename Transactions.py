import sys, os, threading, traceback
import dogecoinrpc, dogecoinrpc.connection, psycopg2
import Config, Logger, Blocknotify

def database():
	return psycopg2.connect(database = Config.config["database"])

def daemon():
	return dogecoinrpc.connect_to_local()

cur = database().cursor()
cur.execute("SELECT block FROM lastblock")
lastblock = cur.fetchone()[0]
del cur

class NotEnoughMoney(Exception):
	pass
InsufficientFunds = dogecoinrpc.exceptions.InsufficientFunds

unconfirmed = {}

# Monkey-patching dogecoinrpc
def patchedlistsinceblock(self, block_hash, minconf=1):
	res = self.proxy.listsinceblock(block_hash, minconf)
	res['transactions'] = [dogecoinrpc.connection.TransactionInfo(**x) for x in res['transactions']]
	return res
try:
	daemon().listsinceblock("0", 1)
except TypeError:
	dogecoinrpc.connection.DogecoinConnection.listsinceblock = patchedlistsinceblock

# Enf of monkey-patching

def notify_block(): 
	global lastblock, unconfirmed
	lb = daemon().listsinceblock(lastblock, Config.config["confirmations"])
	db = database()
	cur = db.cursor()
	txlist = [(int(tx.amount), tx.address) for tx in lb["transactions"] if tx.category == "receive" and tx.confirmations >= Config.config["confirmations"]]
	if len(txlist):
		addrlist = [(tx[1],) for tx in txlist]
		cur.executemany("UPDATE accounts SET balance = balance + %s FROM address_account WHERE accounts.account = address_account.account AND address_account.address = %s", txlist)
		cur.executemany("UPDATE address_account SET used = '1' WHERE address = %s", addrlist)
	unconfirmed = {}
	for tx in lb["transactions"]:
		if tx.category == "receive":
			cur.execute("SELECT account FROM address_account WHERE address = %s", (tx.address,))
			if cur.rowcount:
				account = cur.fetchone()[0]
				if tx.confirmations < Config.config["confirmations"]:
						unconfirmed[account] = unconfirmed.get(account, 0) + int(tx.amount)
				else:
					with Logger.token() as token:
						token.log("t", "deposited %d to %s, TX id is %s {%s + %d}" % (int(tx.amount), tx.address.encode("ascii"), tx.txid.encode("ascii"), account, int(tx.amount)))
	cur.execute("UPDATE lastblock SET block = %s", (lb["lastblock"],))
	db.commit()
	lastblock = lb["lastblock"]

def balance(account): 
	cur = database().cursor()
	cur.execute("SELECT balance FROM accounts WHERE account = %s", (account,))
	if cur.rowcount:
		return cur.fetchone()[0]
	else:
		return 0

def balance_unconfirmed(account):
	return unconfirmed.get(account, 0)

def tip(token, source, target, amount): 
	db = database()
	cur = db.cursor()
	token.log("t", "tipping %d from %s to %s" % (amount, source, target))
	try:
		cur.execute("UPDATE accounts SET balance = balance - %s WHERE account = %s", (amount, source))
	except psycopg2.IntegrityError as e:
		token.log("te", "not enough money")
		raise NotEnoughMoney()
	if not cur.rowcount:
		token.log("te", "not enough money")
		raise NotEnoughMoney()
	token.log("t", "{%s - %d}" % (source, amount))
	cur.execute("UPDATE accounts SET balance = balance + %s WHERE account = %s", (amount, target)) 
	if cur.rowcount:
		token.log("t", "{%s + %d}" % (target, amount))
	else:
		cur.execute("INSERT INTO accounts VALUES (%s, %s)", (target, amount))
		token.log("t", "no rows affected {%s = %d}" % (target, amount))
	db.commit()

def tip_multiple(token, source, dict):
	db = database()
	cur = db.cursor()
	spent = 0
	for target in dict:
		amount = dict[target]
		token.log("t", "tipping %d from %s to %s" % (amount, source, target))
		try:
			cur.execute("UPDATE accounts SET balance = balance - %s WHERE account = %s", (amount, source))
		except psycopg2.IntegrityError as e:
			token.log("te", "not enough money")
			raise NotEnoughMoney()
		if not cur.rowcount:
			token.log("te", "not enough money")
			raise NotEnoughMoney()
		spent += amount
		cur.execute("UPDATE accounts SET balance = balance + %s WHERE account = %s", (amount, target)) 
		if not cur.rowcount:
			cur.execute("INSERT INTO accounts VALUES (%s, %s)", (target, amount))
	token.log("t", "{%s - %d}" % (source, spent))
	for target in dict:
		token.log("t", "{%s + %d}" % (target, dict[target]))
	db.commit()

def withdraw(token, account, address, amount): 
	db = database()
	cur = db.cursor()
	token.log("t", "withdrawing %d from %s to %s" % (amount, account, address))
	try:
		cur.execute("UPDATE accounts SET balance = balance - %s WHERE account = %s", (amount + 1, account))
	except psycopg2.IntegrityError as e:
		token.log("te", "not enough money")
		raise NotEnoughMoney()
	if not cur.rowcount:
		token.log("te", "not enough money")
		raise NotEnoughMoney()
	try:
		tx = daemon().sendtoaddress(address, amount, comment = "sent with Doger")
	except InsufficientFunds:
		token.log("te", "insufficient funds")
		raise
	except:
		token.log("te", "error, locking account")
		Logger.irclog("Emergency lock on account '%s'" % (account))
		lock(account, True)
		raise
	token.log("t", "{%s - %d}" % (account, amount))
	db.commit()
	token.log("t", "TX id is %s" % (tx.encode("ascii")))
	return tx.encode("ascii")

def deposit_address(account): 
	db = database()
	cur = db.cursor()
	cur.execute("SELECT address FROM address_account WHERE used = '0' AND account = %s LIMIT 1", (account,))
	if cur.rowcount:
		return cur.fetchone()[0]
	addr = daemon().getnewaddress()
	try:
		cur.execute("SELECT * FROM accounts WHERE account = %s", (account,))
		if not cur.rowcount:
			cur.execute("INSERT INTO accounts VALUES (%s, 0)", (account,))
		cur.execute("INSERT INTO address_account VALUES (%s, %s, '0')", (addr, account))
		db.commit()
	except:
		pass
	return addr.encode("ascii")

def verify_address(address):
	return daemon().validateaddress(address).isvalid

def balances():
	cur = database().cursor()
	cur.execute("SELECT SUM(balance) FROM accounts")
	database = float(cur.fetchone()[0])
	dogecoind = float(daemon().getbalance(minconf = Config.config["confirmations"]))
	return (database, dogecoind)

def lock(account, state = None):
	if state == None:
		cur = database().cursor()
		cur.execute("SELECT * FROM locked WHERE account = %s", (account,))
		return not not cur.rowcount
	elif state == True:
		db = database()
		cur = db.cursor()
		try:
			cur.execute("INSERT INTO locked VALUES (%s)", (account,))
			db.commit()
		except psycopg2.IntegrityError as e:
			pass
	elif state == False:
		db = database()
		cur = db.cursor()
		cur.execute("DELETE FROM locked WHERE account = %s", (account,))
		db.commit()

