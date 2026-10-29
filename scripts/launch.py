"""Start JARVIS on loopback and open the local browser interface."""
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
URL='http://127.0.0.1:8765'

def health():
    # Local loopback traffic must never go to a system HTTP proxy.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(URL+'/api/health',timeout=1) as r:
        return json.load(r).get('backend')=='connected'

def open_when_ready():
    for _ in range(60):
        try:
            if health():
                webbrowser.open(URL,new=2)
                return
        except (OSError,ValueError):pass
        time.sleep(.25)
    print('Browser startup timed out. Read the server error above.')

if __name__=='__main__':
    with socket.socket() as probe:
        in_use=probe.connect_ex(('127.0.0.1',8765))==0
    if in_use:
        try:
            if health():
                webbrowser.open(URL,new=2)
                print('JARVIS is already running. Reusing the local server.')
                sys.exit(0)
        except (OSError,ValueError):pass
        sys.exit('Port 8765 is occupied by another service. Close that service before launching JARVIS.')
    threading.Thread(target=open_when_ready,daemon=True).start()
    import uvicorn
    print('JARVIS is starting. Keep this window open. Press Ctrl+C here to stop.')
    # Access logging is disabled so user prompts and local session tokens never enter it.
    uvicorn.run('backend.app:app',host='127.0.0.1',port=8765,access_log=False)
