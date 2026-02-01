"""
Quick OIDC Test Server for Homebox.

Usage:
    uv run python tests/run_oidc_test.py

This starts a local web server and opens the OIDC test page in your browser.
"""

import http.server
import os
import socketserver
import webbrowser
from pathlib import Path

PORT = 8765
DIRECTORY = Path(__file__).parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def end_headers(self):
        # Add CORS headers for testing
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


def main():
    os.chdir(DIRECTORY)

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/oidc_test.html"
        print("\n🔐 Homebox OIDC Test Server")
        print(f"   Open: {url}")
        print("   Press Ctrl+C to stop\n")

        # Open browser
        webbrowser.open(url)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")


if __name__ == "__main__":
    main()
