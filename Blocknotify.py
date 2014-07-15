import pyinotify, traceback, threading, os, sys
import Logger, Transactions

blocklock = threading.Lock()
watcher = pyinotify.WatchManager()
class Inotifier(pyinotify.ProcessEvent):
	def process_IN_CREATE(self, event):
		try:
			with blocklock:
				Transactions.notify_block()
		except Exception as e:
			type, value, tb = sys.exc_info()
			Logger.log("te", "ERROR in blocknotify")
			Logger.log("te", repr(e))
			Logger.log("te", "".join(traceback.format_tb(tb)))
		try:
			os.remove(os.path.join(event.path, event.name))
		except:
			pass
notifier = pyinotify.ThreadedNotifier(watcher, Inotifier())
wdd = watcher.add_watch("blocknotify", pyinotify.EventsCodes.ALL_FLAGS["IN_CREATE"])
notifier.start()

def stop():
	notifier.stop()

try:
	os.remove("blocknotify/blocknotify")
except:
	pass
