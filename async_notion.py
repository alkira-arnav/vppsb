import threading
import subprocess
import sys

def run_notion_integrate(repository, pull_request_title):
    subprocess.Popen(["python", "notion_integrate.py", repository, pull_request_title])

t = threading.Thread(target=run_notion_integrate, args=(sys.argv[1], sys.argv[2]))
t.start()
