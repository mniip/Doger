import threading, Queue

instances = {}

ignores = {}
flood_score = {}

whois_lock = threading.Lock()
manager_queue = Queue.Queue()
