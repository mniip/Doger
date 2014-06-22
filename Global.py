import threading, Queue

instances = {}

ignores = {}
flood_score = {}
account_cache = {}

whois_lock = threading.Lock()
manager_queue = Queue.Queue()
