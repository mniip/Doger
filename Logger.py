import Config
import time, md5

def log(spec, text):
# Error Raw Connection Tx Whois Manager
	template = "erctwm"
	specifier = ""
	for c in template:
		specifier += c if c in spec else "_"
	with open(Config.config["logfile"], "a") as f:
		t = time.time()
		for line in text.split("\n"):
			f.write("[%s] [%f] <%s> %s\n" % (time.ctime(t), t, specifier, line))

class Token():
	def __init__(self, id):
		self.id = id

	def __enter__(self):
		log("t", "[%s] Created" % (self.id))
		return self

	def __exit__(self, _, __, ___):
		log("t", "[%s] Destroyed" % (self.id))

	def log(self, spec, text):
		log(spec, "[%s] %s" % (self.id, text))

def token():
	m = md5.new()
	t = time.time()
	m.update(str(t))
	return Token(m.hexdigest()[:8])
