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

def account_name(identity, nick):
	q = Queue.Queue()
	with Global.whois_lock:
		Global.whois_queue[identity].put((nick, q))
		identity_send(identity, "WHOIS", nick)
	return q.get(True)

def account_name_m(identity, nicks):
	qs = []
	for n in nicks:
		assert(len(n))
	for i in range(len(nicks)):
		qs.append(Queue.Queue())
		with Global.whois_lock:
			Global.whois_queue[identity].put((nicks[i], qs[i]))
			identity_send(identity, "WHOIS", nicks[i])
	rs = []
	for i in range(len(nicks)):
		rs.append(qs[i].get(True))
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

def handle_input(identity, line):
	data = parse(line)
	if data[1][0] != '_':
		hook = Hooks.hooks.get(data[1], None)
		if hook:
			hook(identity, data[0], *data[2:])


def reader_thread(identity, sock):
	buffer = ""
	while Global.reader_running[identity]:
		try:
			while buffer.find("\n") != -1:
				line, buffer = buffer.split("\n", 1)
				line = line.rstrip("\r")
				print(identity + ": " + line)
				handle_input(identity, line)
			buffer += sock.recv(4096)
		except socket.timeout:
			pass
		except socket.error:
			Global.writer_running[identity] = False
			Global.reader_running[identity] = False
			Global.write_queue[identity].put(Exception("Disconnecting"))
			Global.write_queue[identity].join()
			connect_identity(identity)
			break
		except Exception as e:
			type, value, tb = sys.exc_info()
			print(identity + " reader ===============")
			traceback.print_tb(tb)
			print(repr(e))
			print(identity + " reader ===============")

def throttle_output(identity, command):
	t = Global.lastsend[identity] - time.time() + 0.25
	if t > 0:
		time.sleep(t)
	Global.lastsend[identity] = time.time()

def writer_thread(identity, sock):
	while Global.writer_running[identity]:
		try:
			q = Global.write_queue[identity]
			data = q.get(True)
			if data is Exception:
				raise data
			print(identity + ": " + repr(data))
			throttle_output(identity, data[0])
			sock.sendall(compile(*data) + "\n")
			q.task_done()
		except Exception as e:
			type, value, tb = sys.exc_info()
			print(identity + " writer ===============")
			traceback.print_tb(tb)
			print(repr(e))
			print(identity + " writer ===============")
			q.task_done()

def identity_send(identity, *args):
	Global.write_queue[identity].put(args)

def spawn_identity(identity):
	Global.write_queue[identity] = Queue.Queue()
	Global.whois_queue[identity] = Queue.Queue()
	connect_identity(identity)

def connect_identity(identity):
	host = random.choice(socket.gethostbyname_ex(Config.config["host"])[2])
	sock = socket.create_connection((host, Config.config["port"]), None)
	sock.settimeout(0.05)
	writer = threading.Thread(target = writer_thread, args = (identity, sock))
	reader = threading.Thread(target = reader_thread, args = (identity, sock))
	Global.writer_running[identity] = True
	Global.lastsend[identity] = 0
	writer.start()
	Global.reader_running[identity] = True
	reader.start()
	identity_send(identity, "NICK", identity)
	identity_send(identity, "USER", Config.config["user"], "*", "*", Config.config["rname"])
	identity_send(identity, "NS", "identify " + Config.config["password"])
