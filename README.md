Doger
=====

IRC tip bot in python.

**Requirements:**

- **RPC library** - From [here](https://github.com/jcsaaddupuy/dogecoin-python) or pypi.
- **Dogecoind** - From [here](https://github.com/dogecoin/dogecoin/), you need the `dogecoind` binary.
- **Postgres** - From [here](http://www.postgresql.org/), python binding from [here](https://pypi.python.org/pypi/psycopg2)
- **Python** - Obviously.

**Setup:**

- Create a file in the same folder as the code named `Config.py`, and put the following into it:

```
config = {
	"host": "ircserverhostna.me",
	"port": 6667,
	"user": "identname",
	"rname": "Real name",
	"confirmations": 4,
	"account": "nickservaccountname",
	"password": "nickservpassword",
	"admins": {
		"unaffiliated/johndoe": True # hosts/cloaks of admins
	},
	"prefix": "!", # the trigger character
# optional:
#	"ssl": {
#		"certs": "/etc/ssl/certs/ca-certificates.crt"
#	},
	"instances": {
		"nick1": ["#channel1", "#channel2"],
		"nick2": ["#channel3"]
	},
# optional:
#	"ignore": {
#		"cost": 10, # score added for every command
#		"limit": 80, # max allowed score
#		"timeout": 240 # ignore length
#	},
	"logfile": "path/to/log",
# optional:
#	"irclog": ("nick1", "#logchannel"),
	"database": "name of pgsql database"
}
```

- Add the following to the dogecoin.conf:

```
rpcthreads=100
daemon=1
irc=0
dnsseed=1
paytxfee=1.0
blocknotify=/usr/bin/touch blocknotify/blocknotify
```

- Create a postgres database with the following schema:

```
CREATE TABLE accounts (account character varying(16) NOT NULL, balance bigint DEFAULT 0, CONSTRAINT balance CHECK ((balance >= 0)));
CREATE TABLE address_account (address character varying(34) NOT NULL, account character varying(16), used bit(1) DEFAULT B'0'::"bit" NOT NULL);
CREATE TABLE locked (account character varying(16));
CREATE TABLE lastblock (block character varying(64));
CREATE TABLE txlog (timestamp double precision, token character varying(8), source character varying(16), destination character varying(16), amount bigint, transaction character varying(64), address character varying(34));
INSERT INTO lastblock VALUES ('0');
ALTER TABLE accounts ADD CONSTRAINT accounts_pkey PRIMARY KEY (account);
ALTER TABLE address_account ADD CONSTRAINT address_account_pkey PRIMARY KEY (address);
ALTER TABLE address_account ADD CONSTRAINT address_account_account_fkey FOREIGN KEY (account) REFERENCES accounts(account);
ALTER TABLE locked ADD CONSTRAINT locked_pkey PRIMARY KEY (account);
```
    
**Running it:**

- Start up the dogecoin daemon (`dogecoind`)
- Launch the bot with `python Main.py`
