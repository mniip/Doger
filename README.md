Doger
=====

IRC tip bot in python.

**Requirements:**

- **RPC library** - From [here](https://github.com/jcsaaddupuy/dogecoin-python) or pypi.
- **Dogecoind** - From [here](https://github.com/dogecoin/dogecoin/), you need the `dogecoind` binary.
- **Python** - Obviously.

**Setup:**

- Create a file in the same folder as the code named `Config.py`, and put the following into it:

```
config = {
	"host": "IRC server hostname",
	"port": 6667,
	"user": "identname",
	"rname": "Real name",
	"password": "nickservpassword",
	"admins": {
		"foo!bar@baz": True # full hostmasks of administrators
	},
	"nicks": {
		"nick1": ["#channel1", "#channel2"],
		"nick2": ["#channel3"]
	}
}
```

- Add the following to the dogecoin.conf:

```
rpcthreads=100
daemon=1
irc=0
dnsseed=1
paytxfee=1.0
```
    
**Running it:**

- Start up the dogecoin daemon (`dogecoind`)
- Launch the bot with `python Main.py`
