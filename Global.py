import threading

write_queue = {}
whois_queue = {}
reader_running = {}
writer_running = {}
flood_score = {}
ignores = {}
lastsend = {}
whois_lock = threading.Lock()
lastwhois = {}
