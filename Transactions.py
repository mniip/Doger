import dogecoinrpc
from dogecoinrpc.exceptions import InsufficientFunds

conn = dogecoinrpc.connect_to_local()

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

"""
def info():
	inf = conn.getinfo()
	return "Blocks: %i, Difficulty: %f, Total balance: %f" % (inf.blocks,inf.difficulty,inf.balance)
"""
