# coding=utf8
import sys, time, threading, traceback

import Global, Transactions, Config, Irc, Logger

if Global.svsevent != None:
	Global.svsevent.set()
Global.svsevent = threading.Event()

def expirer(event):
	try:
		while not event.is_set():
			time.sleep(15)
			cur = Transactions.database().cursor()
			cur.execute("SELECT account FROM accounts WHERE (((last_seen < EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - interval '10 weeks')) IS NOT FALSE AND (last_check < EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - interval '6 hours')) IS NOT FALSE) OR ((last_seen > EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - interval '10 weeks')) IS NOT FALSE AND (last_check < EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - interval '1 week')) IS NOT FALSE)) AND NOT EXISTS (SELECT * FROM locked WHERE locked.account = accounts.account) AND account NOT LIKE '@%' ORDER BY COALESCE(last_check, 0) ASC, balance DESC LIMIT 1")
			if cur.rowcount:
				Irc.instance_send(Config.config["svs"], ("NS", "INFO " + Irc.sanitize_nickname(cur.fetchone()[0])))
	except Exception as e:
		type, value, tb = sys.exc_info()
		Logger.log("te", "ERROR in expirer")
		Logger.log("te", repr(e))
		Logger.log("te", "".join(traceback.format_tb(tb)))
		Logger.irclog("Error in expirer: %s" % (repr(e)))
		Logger.irclog("".join(traceback.format_tb(tb)).replace("\n", " || "))
		del tb
threading.Thread(target = expirer, args = (Global.svsevent,)).start()

def bump_last(acct, t = None):
	if t == None:
		t = int(time.time())
	db = Transactions.database()
	cur = db.cursor()
	cur.execute("UPDATE accounts SET last_seen = %s WHERE account = %s", (t, acct))
	db.commit()

def bump_check(acct):
	db = Transactions.database()
	cur = db.cursor()
	cur.execute("UPDATE accounts SET last_check = EXTRACT(EPOCH FROM CURRENT_TIMESTAMP) WHERE account = %s", (acct,))
	db.commit()


def svsdata(data):
	db = Transactions.database()
	cur = db.cursor()
	cur.execute("SELECT account, last_seen, registered FROM accounts WHERE account = %s", (data["nick"],))
	if cur.rowcount:
		acct, last_seen, registered = cur.fetchone()
		bump_check(acct)
		if "reg" not in data:
			Logger.irclog("Dormant lock on account %s: not registered" % (acct))
			Transactions.lock(acct, True)
		elif registered != None and registered != data["reg"]:
			Logger.irclog("Dormant lock on account %s: registered at %d, remember %d" % (acct, data["reg"], registered))
			Transactions.lock(acct, True)
		else:
			if registered == None:
				cur.execute("SELECT MAX(timestamp) FROM txlog WHERE destination = %s", (acct,))
				lasttx = cur.fetchone()[0] if cur.rowcount else None
				if lasttx != None and lasttx < data["reg"]:
					Logger.irclog("Dormant lock on account %s: registered at %d, last tx at %d" % (acct, data["reg"], lasttx))
					Transactions.lock(acct, True)
				else:
					cur.execute("UPDATE accounts SET registered = %s WHERE account = %s", (data["reg"], acct))
					db.commit()
			if "userlast" in data:
				bump_last(acct, data["userlast"])
			elif "last" in data:
				bump_last(acct, data["last"])
			elif "userlastweeks" in data:
				bump_last(acct, int(time.time()) - (data["userlastweeks"] + 1) * 86400 * 7 - 60)
			elif "lastweeks" in data:
				bump_last(acct, int(time.time()) - (data["lastweeks"] + 1) * 86400 * 7 - 60)
