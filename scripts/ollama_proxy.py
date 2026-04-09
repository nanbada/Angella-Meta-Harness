import http.server
import urllib.request
import json

OLLAMA_URL = "http://127.0.0.1:11434"

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        req = urllib.request.Request(
            f"{OLLAMA_URL}{self.path}",
            data=post_data,
            headers={k: v for k, v in self.headers.items() if k.lower() != 'host'}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                for k, v in response.headers.items():
                    if k.lower() not in ['content-length', 'transfer-encoding', 'connection']:
                        self.send_header(k, v)
                
                if response.info().get_content_type() == 'application/json' or self.path.endswith('/chat') or self.path.endswith('/generate'):
                    # Handle both streaming and non-streaming
                    self.end_headers()
                    for line in response:
                        if not line: continue
                        try:
                            data = json.loads(line.decode('utf-8'))
                            if 'message' in data and 'thinking' in data['message']:
                                del data['message']['thinking']
                            if 'thinking' in data: # top level for some formats
                                del data['thinking']
                            self.wfile.write(json.dumps(data).encode('utf-8') + b'\n')
                        except:
                            self.wfile.write(line)
                else:
                    self.send_header('Content-Length', response.headers.get('Content-Length'))
                    self.end_headers()
                    self.wfile.write(response.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

if __name__ == "__main__":
    print("Starting Improved Ollama Proxy on port 11435...")
    http.server.HTTPServer(('127.0.0.1', 11435), ProxyHandler).serve_forever()
