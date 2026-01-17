"""
Local development server for VBM Visualizer.

Serves static files and proxies Anthropic API calls to keep the API key secure.

Usage:
    python3 server.py

Then open http://localhost:8080 in your browser.
"""

import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Warning: 'requests' library not installed. Run: pip3 install requests")

# Load environment variables from .env file
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

if not ANTHROPIC_API_KEY or 'your-api-key' in ANTHROPIC_API_KEY:
    print("\n" + "="*60)
    print("WARNING: Anthropic API key not configured!")
    print("Edit .env file and set ANTHROPIC_API_KEY=sk-ant-...")
    print("="*60 + "\n")


class VBMHandler(SimpleHTTPRequestHandler):
    """Custom handler that proxies Anthropic API calls."""

    def __init__(self, *args, **kwargs):
        # Serve files from the project root
        super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        """Handle POST requests - proxy to Anthropic API."""
        parsed = urlparse(self.path)

        if parsed.path == '/api/chat':
            self._proxy_anthropic()
        else:
            self.send_error(404, 'Not Found')

    def _proxy_anthropic(self):
        """Proxy a request to Anthropic API."""
        if not HAS_REQUESTS:
            self._send_json_error(500, 'requests library not installed. Run: pip3 install requests')
            return

        if not ANTHROPIC_API_KEY or 'your-api-key' in ANTHROPIC_API_KEY:
            self._send_json_error(500, 'Anthropic API key not configured. Edit .env file.')
            return

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        request_data = json.loads(body)

        # Convert from our format to Anthropic format
        anthropic_body = {
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': request_data.get('max_tokens', 300),
            'system': request_data.get('system', ''),
            'messages': request_data.get('messages', [])
        }

        try:
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                json=anthropic_body,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01'
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                # Convert Anthropic response to simpler format for frontend
                simplified = {
                    'content': result['content'][0]['text'] if result.get('content') else ''
                }
                self._send_json_response(200, simplified)
            else:
                error_msg = response.text
                print(f"Anthropic API error ({response.status_code}): {error_msg}")
                self._send_json_error(response.status_code, f'API error: {error_msg}')

        except requests.exceptions.Timeout:
            self._send_json_error(504, 'Request to Anthropic API timed out')
        except Exception as e:
            print(f"Error: {e}")
            self._send_json_error(500, str(e))

    def _send_json_response(self, status_code, data):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_json_error(self, status_code, message):
        """Send a JSON error response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'error': {'message': message}}).encode())

    def do_GET(self):
        """Handle GET requests - serve static files."""
        parsed = urlparse(self.path)

        # Redirect root to app
        if parsed.path == '/' or parsed.path == '':
            self.send_response(302)
            self.send_header('Location', '/app/index.html')
            self.end_headers()
            return

        # Serve static files
        super().do_GET()

    def log_message(self, format, *args):
        """Custom logging."""
        print(f"[{self.log_date_time_string()}] {args[0]}")


def run_server(port=8080):
    """Start the development server."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, VBMHandler)

    print("\n" + "="*60)
    print("VBM Visualizer - Local Development Server")
    print("="*60)
    print(f"\n  URL: http://localhost:{port}")
    print(f"  API Key: {'Configured' if ANTHROPIC_API_KEY and 'your-api-key' not in ANTHROPIC_API_KEY else 'NOT SET - edit .env'}")
    print(f"  Requests lib: {'OK' if HAS_REQUESTS else 'MISSING - run pip3 install requests'}")
    print("\n  Press Ctrl+C to stop\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == '__main__':
    run_server()
