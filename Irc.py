import socket, random, threading, Queue, sys, traceback, time, ssl
from string import maketrans
import Config, Global, Hooks, Logger

lowercase = "abcdefghijklmnopqrstuvwxyz[]~\\"
uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ{}^|"
caseless = "0123456789_-`@"

ircupper = maketrans(lowercase, uppercase)

def get_nickname(hostmask):
	return hostmask.split("!", 1)[0]

def strip_nickname(name):
	return name.lstrip("+@")

def get_host(hostmask):
	return hostmask.split("@", 1)[1]

def nick_upper(nickname):
	return nickname.translate(ircupper)

def equal_nicks(a, b):
	return nick_upper(a) == nick_upper(b)

def sanitize_nickname(nickname):
	if len(nickname):
		return "".join(c if c in lowercase or c in uppercase or c in caseless else '.' for c in nickname)
	return "."

def is_ignored(host):
	r = Global.ignores.get(host, None)
	if r:
		if r < time.time():
			del Global.ignores[host]
			return False
		return True
	return False

def ignore(host, duration):
	Global.ignores[host] = time.time() + duration

def is_admin(hostmask):
	return Config.config["admins"].get(get_host(hostmask), False)

def account_names(nicks):
	for i in range(len(nicks)):
		nicks[i] = sanitize_nickname(nicks[i])
	queues = [None for _ in nicks]
	results = [None for _ in nicks]
	Logger.log("w", "Task: " + " ".join(nicks))
	for i in range(len(nicks)):
		found = False
		for channel in Global.account_cache:
			for nick in Global.account_cache[channel]:
				if Global.account_cache[channel][nick] != None and equal_nicks(nick, nicks[i]):
					results[i] = Global.account_cache[channel][nick]
					Logger.log("w", "Found %s in cache for %s : %s=%s" % (nicks[i], channel, nick, repr(results[i])))
					found = True
					break
			if found:
				break
		if not found:
			queues[i] = Queue.Queue()
			least = None
			leastsize = float("inf")
			for instance in Global.instances:
				size = Global.instances[instance].whois_queue.unfinished_tasks + Global.instances[instance].send_queue.unfinished_tasks
				if leastsize > size:
					least = instance
					leastsize = size
			Logger.log("w", "Smallest instance for whois is " + least)
			with Global.whois_lock:
				Global.instances[least].whois_queue.put((nicks[i], queues[i]))
				instance_send(least, ("WHOIS", nicks[i]))
	for i in range(len(nicks)):
		if results[i] == None:
			account = queues[i].get(True)
			for channel in Global.account_cache:
				for nick in Global.account_cache[channel]:
					if equal_nicks(nick, nicks[i]):
						Global.account_cache[channel][nick] = account
						Logger.log("w", "Propagating %s=%s into %s" % (nicks[i], repr(account), channel))
			results[i] = account
	Logger.log("w", "Solution: " + " ".join([repr(x) for x in results]))
	return results

def parse(cmd):
	data = cmd.split(" ")
	if data[0][0] != ':':
		data.insert(0, None)
	else:
		data[0] = data[0][1:]
	for i in range(1, len(data)):
		if data[i][0] == ':':
			data[i:] = [(" ".join(data[i:]))[1:]]
			break
	return data

def compile(*args):
	data = list(args)
	data[-1] = ':' + data[-1]
	return " ".join(data)

def handle_input(instance, line):
	data = parse(line)
	if data[1][0] != '_':
		hook = Hooks.hooks.get(data[1], None)
		if hook:
			hook(instance, data[0], *data[2:])

class Instance(object):
	def __init__(self, instance):
		self.can_send = threading.Event()
		self.send_queue = Queue.PriorityQueue()
		self.whois_lock = threading.Lock()
		self.whois_queue = Queue.Queue()
		self.lastsend = time.time()
		self.lastwhois = None
		self.reader_dying = threading.Event()
		self.reader_dead = threading.Event()
		self.writer_dying = threading.Event()
		self.writer_dead = threading.Event()
		self.error_lock = threading.Lock()

def reader_thread(instance, sock):
	Logger.log("c", instance + ": Reader started")
	buffer = ""
	while not Global.instances[instance].reader_dying.is_set():
		try:
			try:
				while buffer.find("\n") != -1:
					line, buffer = buffer.split("\n", 1)
					line = line.rstrip("\r")
					Logger.log("r", instance + ": > " + line)
					handle_input(instance, line)
				buffer += sock.recv(4096)
			except ssl.SSLError as e:
				if e.message == 'The read operation timed out':
					raise socket.timeout()
				else:
					raise e
		except socket.timeout:
			pass
		except socket.error as e:
			Logger.log("ce", instance + ": Reader failed")
			if Global.instances[instance].error_lock.acquire(False):
				type, value, tb = sys.exc_info()
				Logger.log("ce", "SOCKET ERROR in " + instance + " reader")
				Logger.log("ce", repr(e))
				Logger.log("ce", "".join(traceback.format_tb(tb)))
				Global.manager_queue.put(("Reconnect", instance))
				Global.instances[instance].reader_dying.wait()
			else:
				Logger.log("c", instance + ": Reader superfluous error")
			break
		except Exception as e:
			type, value, tb = sys.exc_info()
			Logger.log("ce", "ERROR in " + instance + " reader")
			Logger.log("ce", repr(e))
			Logger.log("ce", "".join(traceback.format_tb(tb)))
	try:
		sock.close()
	except socket.error:
		pass
	Global.instances[instance].reader_dead.set()
	Logger.log("c", instance + ": Reader exited")


def throttle_output(instance):
	t = Global.instances[instance].lastsend - time.time() + 0.5
	if t > 0:
		time.sleep(t)
	Global.instances[instance].lastsend = time.time()

def writer_thread(instance, sock):
	Logger.log("c", instance + ": Writer started")
	while not Global.instances[instance].writer_dying.is_set():
		try:
			if Global.instances[instance].lastsend + 300 < time.time():
				raise socket.error("Timeout")
			q = Global.instances[instance].send_queue
			data = q.get(True, 0.5)[2]
			throttle_output(instance)
			line = compile(*data)
			Logger.log("r", instance + ": < " + line)
			sock.sendall(line + "\n")
			q.task_done()
		except Queue.Empty:
			pass
		except socket.error as e:
			if e.message != "Timeout":
				q.task_done()
			Logger.log("ce", instance + ": Writer failed")
			if Global.instances[instance].error_lock.acquire(False):
				type, value, tb = sys.exc_info()
				Logger.log("ce", "SOCKET ERROR in " + instance + " writer")
				Logger.log("ce", repr(e))
				Logger.log("ce", "".join(traceback.format_tb(tb)))
				Global.manager_queue.put(("Reconnect", instance))
				Global.instances[instance].writer_dying.wait()
			else:
				Logger.log("c", instance + ": Writer superfluous error")
			break
		except Exception as e:
			q.task_done()
			type, value, tb = sys.exc_info()
			Logger.log("ce", "ERROR in " + instance + " writer")
			Logger.log("ce", repr(e))
			Logger.log("ce", "".join(traceback.format_tb(tb)))
	try:
		sock.close()
	except socket.error:
		pass
	Global.instances[instance].writer_dead.set()
	Logger.log("c", instance + ": Writer exited")

def instance_send(instance, args, priority = 1, lock = True):
	if lock:
		Global.instances[instance].can_send.wait()
	Global.instances[instance].send_queue.put((priority, time.time(), args))

def connect_instance(instance):
	Logger.log("c", instance + ": Connecting")
	host = random.choice(socket.gethostbyname_ex(Config.config["host"])[2])
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	if Config.config.get("ssl", None):
		sock = ssl.wrap_socket(sock, ca_certs = Config.config["ssl"]["certs"], cert_reqs = ssl.CERT_REQUIRED)
	sock.connect((host, Config.config["port"]))
	sock.settimeout(0.1)
	writer = threading.Thread(target = writer_thread, args = (instance, sock))
	reader = threading.Thread(target = reader_thread, args = (instance, sock))
	Global.instances[instance].reader_dying.clear()
	Global.instances[instance].reader_dead.clear()
	Global.instances[instance].writer_dying.clear()
	Global.instances[instance].writer_dead.clear()
	Global.instances[instance].lastsend = time.time()
	writer.start()
	reader.start()
	Logger.log("c", instance + ": Initiating authentication")
	instance_send(instance, ("CAP", "REQ", "sasl"), lock = False)
	instance_send(instance, ("NICK", instance), lock = False)
	instance_send(instance, ("USER", Config.config["user"], "*", "*", Config.config["rname"]), lock = False)

def manager():
	while True:
		try:
			cmd = Global.manager_queue.get(True)
			Logger.log("m", "Got " + repr(cmd))
			if cmd[0] == "Spawn":
				i = Instance(cmd[1])
				i.can_send.clear()
				Global.instances[cmd[1]] = i
				connect_instance(cmd[1])
			elif cmd[0] == "Reconnect" or cmd[0] == "Disconnect":
				Global.instances[cmd[1]].can_send.clear()
				Global.instances[cmd[1]].reader_dying.set()
				Global.instances[cmd[1]].writer_dying.set()
				Logger.log("m", "Waiting for reader")
				Global.instances[cmd[1]].reader_dead.wait()
				Logger.log("m", "Waiting for writer")
				Global.instances[cmd[1]].writer_dead.wait()
				Logger.log("m", "Emptying send queue")
				try:
					while True:
						Global.instances[cmd[1]].send_queue.get(False)
				except Queue.Empty:
					pass
				Logger.log("mw", "Emptying whois queue")
				try:
					while True:
						Global.instances[cmd[1]].whois_queue.get(False)[1].put(None)
						Global.instances[cmd[1]].whois_queue.task_done()
				except Queue.Empty:
					pass
				chans = []
				for channel in Global.account_cache:
					if cmd[1] in Global.account_cache[channel]:
						chans.append(channel)
				if cmd[0] == "Reconnect":
					connect_instance(cmd[1])
				else:
					del Global.instances[cmd[1]]
			elif cmd[0] == "Die":
				Logger.log("m", "Dying")
				return
		except Exception as e:
			type, value, tb = sys.exc_info()
			Logger.log("me", "ERROR in manager")
			Logger.log("me", repr(e))
			Logger.log("me", "".join(traceback.format_tb(tb)))
		Global.manager_queue.task_done()
		Logger.log("m", "Done")
