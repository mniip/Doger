import sys, os, threading, pyinotify
import dogecoinrpc, psycopg2
import Config, Logger

conn = dogecoinrpc.connect_to_local()

def connect():
	return psycopg2.connect(database = "doger")

cur = connect().cursor()
cur.execute("SELECT block FROM lastblock")
lastblock = cur.fetchone()[0]
del cur

blocklock = threading.Lock()
watcher = pyinotify.WatchManager()
class Inotifier(pyinotify.ProcessEvent):
	def process_IN_CREATE(self, event):
		try:
			with blocklock:
				notify_block()
		except Exception as e:
			type, value, tb = sys.exc_info()
			Logger.log("te", "ERROR in blocknotify")
			Logger.log("te", repr(e))
			Logger.log("te", "".join(traceback.format_tb(tb)))
			pass
		finally:
			os.remove(os.path.join(event.path, event.name))
notifier = pyinotify.ThreadedNotifier(watcher, Inotifier())
wdd = watcher.add_watch("blocknotify", pyinotify.EventsCodes.ALL_FLAGS["IN_CREATE"])
notifier.start()

class NotEnoughMoney(Exception):
	pass
InsufficientFunds = dogecoinrpc.exceptions.InsufficientFunds

unconfirmed = {}

def notify_block(): 
	global lastblock, unconfirmed
	lb = conn.listsinceblock(lastblock, 4)
	db = connect()
	cur = db.cursor()
	txlist = [(int(tx.amount), tx.address) for tx in lb["transactions"] if tx.category == "receive" and tx.confirmations >= Config.config["confirmations"]]
	if len(txlist):
		addrlist = [(tx[1],) for tx in txlist]
		cur.executemany("UPDATE accounts SET balance = balance + %s FROM address_account WHERE accounts.account = address_account.account AND address_account.address = %s", txlist)
		cur.executemany("UPDATE address_account SET used = '1' WHERE address = %s", addrlist)
	unconfirmed = {}
	for tx in lb["transactions"]:
		if tx.category == "receive":
			if tx.confirmations < Config.config["confirmations"]:
				cur.execute("SELECT account FROM address_account WHERE address = %s", (tx.address,))
				if cur.rowcount:
					account = cur.fetchone()[0]
					unconfirmed[account] = unconfirmed.get(account, 0) + int(tx.amount)
			else:
				with Logger.token() as token:
					token.log("t", "deposited %d to %s, TX id is %s" % (int(tx.amount), tx.address.encode("ascii"), tx.txid.encode("ascii")))
	cur.execute("UPDATE lastblock SET block = %s", (lb["lastblock"],))
	db.commit()
	lastblock = lb["lastblock"]

notify_block()
try:
	os.remove("blocknotify/blocknotify")
except OSError:
	pass

def balance(account): 
	cur = connect().cursor()
	cur.execute("SELECT balance FROM accounts WHERE account = %s", (account,))
	if cur.rowcount:
		return cur.fetchone()[0]
	else:
		return 0

def balance_unconfirmed(account):
	return unconfirmed.get(account, 0)

def tip(source, target, amount): 
	db = connect()
	cur = db.cursor()
	try:
		cur.execute("UPDATE accounts SET balance = balance - %s WHERE account = %s", (amount, source))
	except psycopg2.IntegrityError as e:
		raise NotEnoughMoney()
	if not cur.rowcount:
		raise NotEnoughMoney()
	cur.execute("UPDATE accounts SET balance = balance + %s WHERE account = %s", (amount, target)) 
	if not cur.rowcount:
		cur.execute("INSERT INTO accounts VALUES (%s, %s)", (target, amount))
	db.commit()

def tip_multiple(source, dict):
	db = connect()
	cur = db.cursor()
	for target in dict:
		amount = dict[target]
		try:
			cur.execute("UPDATE accounts SET balance = balance - %s WHERE account = %s", (amount, source))
		except psycopg2.IntegrityError as e:
			raise NotEnoughMoney()
		if not cur.rowcount:
			raise NotEnoughMoney()
		cur.execute("UPDATE accounts SET balance = balance + %s WHERE account = %s", (amount, target)) 
		if not cur.rowcount:
			cur.execute("INSERT INTO accounts VALUES (%s, %s)", (target, amount))
	db.commit()

def withdraw(account, address, amount): 
	db = connect()
	cur = db.cursor()
	try:
		cur.execute("UPDATE accounts SET balance = balance - %s WHERE account = %s", (amount + 1, account))
	except psycopg2.IntegrityError as e:
		raise NotEnoughMoney()
	if not cur.rowcount:
		raise NotEnoughMoney()
	try:
	 	tx = conn.sendtoaddress(address, amount, comment = "sent with Doger")
	except Exception as e:
		raise e
	db.commit()
	return tx.encode("ascii")

def deposit_address(account): 
	db = connect()
	cur = db.cursor()
	cur.execute("SELECT address FROM address_account WHERE used = '0' AND account = %s LIMIT 1", (account,))
	if cur.rowcount:
		return cur.fetchone()[0]
	addr = conn.getnewaddress()
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
	return conn.validateaddress(address).isvalid
