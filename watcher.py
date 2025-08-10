# watcher.py
import sys
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class RestartOnChangeHandler(FileSystemEventHandler):
    print('version')
    def __init__(self, command):
        self.command = command
        self.process = subprocess.Popen(command)

    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print(f"{event.src_path} changed. Restarting...")
            self.process.kill()
            self.process = subprocess.Popen(self.command)

if __name__ == "__main__":
    path = "."
    command = [sys.executable, "main.py"]
    event_handler = RestartOnChangeHandler(command)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        event_handler.process.kill()

    observer.join()
