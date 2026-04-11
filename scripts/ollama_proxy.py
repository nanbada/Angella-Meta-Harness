import http.server
import urllib.request
import json
import re

OLLAMA_URL = "http://127.0.0.1:11434"

# Pre-compile regex for performance (Boris Cherny point 1)
TOOL_CALL_PATTERN = re.compile(r'<\|tool_call\|>(.*?)<\|/tool_call\|>', re.DOTALL)

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def _extract_gemma4_tool_call(self, content: str) -> str:
        """Surgically extract tool-call from native tags."""
        match = TOOL_CALL_PATTERN.search(content)
        if match:
            return match.group(1).strip()
        
        # Fallback for raw JSON produced by 4-bit models
        trimmed = content.strip()
        if trimmed.startswith('{') and trimmed.endswith('}'):
            return trimmed
            
        return content

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
                    self.end_headers()
                    for line in response:
                        if not line: continue
                        try:
                            data = json.loads(line.decode('utf-8'))
                            
                            # 1. Strip thinking fields (Zero-Overhead for clean context)
                            if 'message' in data and 'thinking' in data['message']:
                                del data['message']['thinking']
                            if 'thinking' in data:
                                del data['thinking']
                            
                            # 2. Intercept and parse Tool-Calls for Gemma 4 (Pre-computing upfront)
                            if 'message' in data and 'content' in data['message']:
                                content = data['message']['content']
                                if '<|tool_call|>' in content:
                                    data['message']['content'] = self._extract_gemma4_tool_call(content)
                            elif 'response' in data: # /api/generate
                                response_text = data['response']
                                if '<|tool_call|>' in response_text:
                                    data['response'] = self._extract_gemma4_tool_call(response_text)
                                    
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
