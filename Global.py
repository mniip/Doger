import threading, Queue

instances = {}

ignores = {}
flood_score = {}

account_cache = {}
account_lock = threading.Lock()

whois_lock = threading.Lock()
manager_queue = Queue.Queue()
