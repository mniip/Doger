import threading, time, os
import dogecoinrpc
from dogecoinrpc.exceptions import InsufficientFunds, WalletError

conn = dogecoinrpc.connect_to_local()
conn.proxy._transport.connection.timeout = 600
lock = threading.Lock()

class RpcLock(object):
	def __enter__(self):
		lock.acquire()
	
	def __exit__(self, _, __, ___):
		lock.release()

rpclock = RpcLock()

def get_lock():
	return rpclock

def tip(acct1, acct2, amt):
	if amt < 1:
		return False
	if balance(acct1) < amt:
		return False
	try:
	    conn.move(acct1, acct2, amt)
	    return True
	except:
	    return False

def deposit_address(acct):
	addrs = conn.getaddressesbyaccount(acct)
	if len(addrs) > 0:
		return addrs[0]
	else:
		return conn.getnewaddress(acct)

def balance(acct, minconf = 4):
	return conn.getbalance(acct, minconf = minconf)

def withdraw(acct, addr, amt):
	try:
		tx = conn.sendfrom(acct, addr, amt, comment = 'sent with Doger')
		return tx
	except:
		return False

def verify_address(addr):
	inf = conn.validateaddress(addr)
	return inf.isvalid

def renew_wallet():
	global conn
	assert(False)
	i = 0
	try:
		while True:
			open(".dogecoin/renew_wallet.log." + str(i), "r").close()
			i += 1
	except IOError:
		pass
	conn.backupwallet(".dogecoin/wallet.bak." + str(i))
	balances = {}
	with open(".dogecoin/renew_wallet.log." + str(i), "w", 0) as f:
		master = None
		for user in conn.listaccounts():
			balance = float(conn.getbalance(user, minconf = 4))
			if balance:
				balances[user] = balance
				f.write("DUMP\tuser\t%d\t%s\n" % (balances[user], user.encode("utf8")))
				for wallet in conn.getaddressesbyaccount(user):
					f.write("DUMP\twallet\t%s\t%s\t%s\n" % (wallet, conn.dumpprivkey(wallet), user.encode("utf8")))
					if user == "":
						master = wallet
		print(repr(balances))
		if not master:
			master = conn.getnewaddress("")
		total = 0.0
		for user in balances:
			conn.move(user, "", balances[user])
			total += balances[user]
		masterkey = conn.dumpprivkey(master)
		f.write("DUMP\tmaster\t%s\t%s\t%d\n" % (master, masterkey, total))
		fee = 0
		tx = None
		while True:
			try:
				tx = conn.sendfrom("", master, total - fee, comment = 'Renewing wallet')
				break
			except WalletError, InsufficientFunds:
				fee += 1
		f.write("DUMP\tsend\t%d\t%d\t%s\n" % (total, -fee, tx.encode("utf8")))
		time.sleep(20)
		conn.stop()
		conn.proxy._transport.connection.close()
		try:
			while True:
				open(".dogecoin/dogecoind.pid", "r").close()
				time.sleep(0.1)
		except IOError:
			pass
		f.write("DUMP\tdaemon dead\n")
		os.rename(".dogecoin/wallet.dat", ".dogecoin/wallet.bak.bak." + str(i))
		os.system("./dogecoind")
		f.write("RESTORE\tdaemon started\n")
		while True:
			try:
				conn = dogecoinrpc.connect_to_local()
				conn.proxy._transport.connection.timeout = 600
				conn.getinfo()
				break
			except Exception as e:
				print(repr(e))
				conn.proxy._transport.connection.close()
				time.sleep(1)
		conn.importprivkey(masterkey, "", True)
		f.write("RESTORE\tmaster\t%s\t%s\n" % (conn.getaddressesbyaccount("")[0], masterkey))
		for user in balances:
			try:
				conn.move("", user, int(balances[user]))
				f.write("RESTORE\tuser\t%d\t%s\n" % (int(conn.getbalance(user, minconf = 0)), user))
			except:
				f.write("RESTORE\tfail\t%d!=%d\t%s\n" % (int(conn.getbalance(user, minconf = 0)), balances[user], user))
		if fee:
			conn.move("@DONATIONS", "", fee)
		f.write("DONE\n")
