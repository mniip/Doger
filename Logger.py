import time, md5

logfile = "Doger.log"

def log(id, text):
	with open(logfile, "a") as f:
		if id:
			f.write(str(id) + "\t" + str(text) + "\n")
		else:
			f.write("\t" + str(text) + "\n")

def get_id():
	m = md5.new()
	t = time.time()
	m.update(str(t))
	id = m.hexdigest()[:8]
	log(id, "Created at %f" % (t))
	return id


