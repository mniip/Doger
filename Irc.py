import socket, random, threading, Queue, sys, traceback, time
from string import maketrans
import Config, Global, Hooks

ircupper = maketrans(
	"abcdefghijklmnopqrstuvwxyz[]~\\",
	"ABCDEFGHIJKLMNOPQRSTUVWXYZ{}^|")

def get_nickname(hostmask):
	return hostmask.split("!", 1)[0]

def get_host(hostmask):
	return hostmask.split("@", 1)[1]

def nick_upper(nickname):
	return nickname.translate(ircupper)

def equal_nicks(a, b):
	return nick_upper(a) == nick_upper(b)

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
	return Config.config["admins"].get(hostmask, False)

whois_cache = {}

def account_name(nick):
	try:
		(last, account) = whois_cache[nick_upper(nick)]
		if time.time() < last + 0.1:
			return account
	except KeyError:
		pass
	q = Queue.Queue()
	least = None
	leastsize = float("inf")
	for instance in Global.instances:
		qs = Global.instances[instance].whois_queue.unfinished_tasks
		if leastsize > qs:
			least = instance
			leastsize = qs
	print("least=" + least)
	with Global.whois_lock:
		print("sent to " + repr(Global.instances[least].whois_queue))
		Global.instances[least].whois_queue.put((nick, q))
		instance_send(least, "WHOIS", nick)
	account = q.get(True)
	whois_cache[nick_upper(nick)] = (time.time(), account)
	return account

def account_name_m(nicks):
	for n in nicks:
		assert(len(n))
	qs = [Queue.Queue() for _ in nicks]
	rs = [None for _ in nicks]
	t = time.time()
	for i in range(len(nicks)):
		try:
			(last, account) = whois_cache[nick_upper(nicks[i])]
			print(last,account)
			if t < last + 0.1:
				rs[i] = account
			else:
				raise KeyError()
		except KeyError:
			least = None
			leastsize = float("inf")
			for instance in Global.instances:
				size = Global.instances[instance].whois_queue.unfinished_tasks
				if leastsize > size:
					least = instance
					leastsize = size
			print("least=" + least)
			with Global.whois_lock:
				Global.instances[least].whois_queue.put((nicks[i], qs[i]))
				instance_send(least, "WHOIS", nicks[i])
	print(repr(rs))
	for i in range(len(nicks)):
		if not rs[i]:
			account = qs[i].get(True)
			whois_cache[nick_upper(nicks[i])] = (time.time(), account)
			rs[i] = account
	return rs

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
		self.send_lock = threading.Lock()
		self.send_queue = Queue.Queue()
		self.whois_lock = threading.Lock()
		self.whois_queue = Queue.Queue()
		self.lastsend = 0
		self.reader_dying = threading.Event()
		self.reader_dead = threading.Event()
		self.writer_dying = threading.Event()
		self.writer_dead = threading.Event()

def reader_thread(instance, sock):
	print(instance + " reader started")
	buffer = ""
	while not Global.instances[instance].reader_dying.is_set():
		try:
			while buffer.find("\n") != -1:
				line, buffer = buffer.split("\n", 1)
				line = line.rstrip("\r")
				print(instance + ": " + line)
				handle_input(instance, line)
			buffer += sock.recv(4096)
		except socket.timeout:
			pass
		except socket.error as e:
			print(instance + " reader failed: " + repr(e))
			Global.manager_queue.put(("Reconnect", instance))
			Global.instances[instance].reader_dying.wait()
			break
		except Exception as e:
			type, value, tb = sys.exc_info()
			print(instance + " reader ===============")
			traceback.print_tb(tb)
			print(repr(e))
			print(instance + " reader ===============")
	print(instance + " reader exited")
	try:
		sock.close()
	except socket.error:
		pass
	Global.instances[instance].reader_dead.set()

throttle_exempt = {"WHOIS": 0.5}

def throttle_output(instance, command):
	t = Global.instances[instance].lastsend - time.time() + throttle_exempt.get(command, 0.25)
	if t > 0:
		time.sleep(t)
	Global.instances[instance].lastsend = time.time()

def writer_thread(instance, sock):
	print(instance + " writer started")
	while not Global.instances[instance].writer_dying.is_set():
		try:
			q = Global.instances[instance].send_queue
			data = q.get(True, 0.05)
			print(instance + ": " + repr(data))
			throttle_output(instance, data[0])
			sock.sendall(compile(*data) + "\n")
		except Queue.Empty:
			pass
		except socket.error as e:
			q.task_done()
			print(instance + " writer failed: " + repr(e))
			Global.manager_queue.put(("Reconnect", instance))
			Global.instances[instance].writer_dying.wait()
			break
		except Exception as e:
			q.task_done()
			type, value, tb = sys.exc_info()
			print(instance + " writer ===============")
			traceback.print_tb(tb)
			print(repr(e))
			print(instance + " writer ===============")
	print(instance + " writer exited")
	try:
		sock.close()
	except socket.error:
		pass
	Global.instances[instance].writer_dead.set()

def instance_send(instance, *args):
	with Global.instances[instance].send_lock:
		Global.instances[instance].send_queue.put(args)

def instance_send_nolock(instance, *args):
	Global.instances[instance].send_queue.put(args)

def connect_instance(instance):
	host = random.choice(socket.gethostbyname_ex(Config.config["host"])[2])
	sock = socket.create_connection((host, Config.config["port"]), None)
	sock.settimeout(0.05)
	writer = threading.Thread(target = writer_thread, args = (instance, sock))
	reader = threading.Thread(target = reader_thread, args = (instance, sock))
	Global.instances[instance].reader_dying.clear()
	Global.instances[instance].reader_dead.clear()
	Global.instances[instance].writer_dying.clear()
	Global.instances[instance].writer_dead.clear()
	Global.instances[instance].lastsend = 0
	writer.start()
	reader.start()
	instance_send_nolock(instance, "NICK", instance)
	instance_send_nolock(instance, "USER", Config.config["user"], "*", "*", Config.config["rname"])
	instance_send_nolock(instance, "NS", "identify " + Config.config["account"] + " " + Config.config["password"])

def manager():
	while True:
		try:
			cmd = Global.manager_queue.get(True)
			print(repr(cmd))
			if cmd[0] == "Spawn":
				i = Instance(cmd[1])
				i.send_lock.acquire()
				Global.instances[cmd[1]] = i
				connect_instance(cmd[1])
			elif cmd[0] == "Reconnect":
				Global.instances[cmd[1]].send_lock.acquire()
				Global.instances[cmd[1]].reader_dying.set()
				Global.instances[cmd[1]].writer_dying.set()
				Global.instances[cmd[1]].reader_dead.wait()
				Global.instances[cmd[1]].writer_dead.wait()
				try:
					while True:
						Global.instances[cmd[1]].send_queue.get(False)
				except Queue.Empty:
					pass
				try:
					while True:
						Global.instances[cmd[1]].whois_queue.get(False)[1].put(None)
						Global.instances[cmd[1]].whois_queue.task_done()
				except Queue.Empty:
					pass
				connect_instance(cmd[1])
			elif cmd[0] == "Disconnect":
				Global.instances[cmd[1]].send_lock.acquire()
				Global.instances[cmd[1]].reader_dying.set()
				Global.instances[cmd[1]].writer_dying.set()
				Global.instances[cmd[1]].reader_dead.wait()
				Global.instances[cmd[1]].writer_dead.wait()
				try:
					while True:
						Global.instances[cmd[1]].send_queue.get(False)
				except Queue.Empty:
					pass
				try:
					while True:
						Global.instances[cmd[1]].whois_queue.get(False)[1].put(None)
						Global.instances[cmd[1]].whois_queue.task_done()
				except Queue.Empty:
					pass
				del Global.instances[cmd[1]]
			elif cmd[0] == "Die":
				return
		except Exception as e:
			type, value, tb = sys.exc_info()
			print(instance + " manager ===============")
			traceback.print_tb(tb)
			print(repr(e))
			print(instance + " manager ===============")
		Global.manager_queue.task_done()
