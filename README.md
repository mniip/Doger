Doger
=====

IRC tip bot in python.

**Requirements:**

- **RPC library** - From [here](https://github.com/jcsaaddupuy/dogecoin-python) or pypi.
- **Dogecoind** - From [here](https://github.com/dogecoin/dogecoin/), you need the `dogecoind` binary.
- **Python** - Obviously.

**Setup:**

- Create a file in the same folder as the code named `config.py`, and put the following into it:

```
    {
    	"host": "hostname of irc server",
    	"port": 6667,
    	"nick": "nickname",
    	"user": "username",
    	"rname": "real name",
    	"password": "Nickserv Password",
    	"autojoin": ["#channel to join","#another channel to join"],
    	"admins": {
    		"nick!username@hostname of admin": True
    		"more as needed...": True
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
