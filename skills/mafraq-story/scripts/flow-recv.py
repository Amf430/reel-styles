"""Local receiver for Google Flow downloads: the browser POSTs each blob to http://127.0.0.1:8799/<name>.jpg.
Usage: python3 flow-recv.py <out_dir>   (stop with Ctrl-C)"""
import http.server, os, re, sys
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
class H(http.server.BaseHTTPRequestHandler):
    def cors(self):
        self.send_header('Access-Control-Allow-Origin', 'https://flow.google.com')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()
    def do_POST(self):
        name = re.sub(r'[^A-Za-z0-9._-]', '_', self.path.strip('/')) or 'file.bin'
        n = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(n)
        with open(os.path.join(OUT, name), 'wb') as f: f.write(data)
        self.send_response(200); self.cors(); self.end_headers(); self.wfile.write(b'ok')
        print('saved', name, len(data), flush=True)
http.server.HTTPServer(('127.0.0.1', 8799), H).serve_forever()
