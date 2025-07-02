#!/usr/bin/env python3

import http.server
import socketserver
import time
import os

DELAY = 2
PROJECT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
DIRECTORY = os.path.join(PROJECT_DIR, "dist")
PORT = 3000
BIND_ADDRESS = "127.0.0.1"


class DelayHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        os.chdir(DIRECTORY)
        super().__init__(*args, **kwargs)

    def do_GET(self):
        time.sleep(DELAY)
        super().do_GET()


handler = DelayHTTPRequestHandler

with socketserver.TCPServer((BIND_ADDRESS, PORT), handler) as httpd:
    print(f"Serving {BIND_ADDRESS}:{PORT}")
    print(f"Directory: {os.path.relpath(DIRECTORY, PROJECT_DIR)}")
    print(f"Delay: {DELAY}s")
    httpd.serve_forever()
