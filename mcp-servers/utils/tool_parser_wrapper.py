#!/usr/bin/env python3
"""
MCP Server for Gemma 4 Tool-Call Parsing & Interception.
Helps the harness handle native Gemma 4 <|tool_call|> tags and 
corrects common 4-bit hallucination patterns in JSON output.
"""
import json
import re
import sys

def intercept_gemma4_tool_call(output: str) -> str:
    """
    Parses Gemma 4 native <|tool_call|> ... <|/tool_call|> blocks
    and extracts the JSON content.
    """
    match = re.search(r'<\|tool_call\|>(.*?)<\|/tool_call\|>', output, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Fallback: check for raw JSON if tags are missing but structure looks like JSON
    if output.strip().startswith('{') and output.strip().endswith('}'):
        return output.strip()
        
    return output

def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    tool = request.get("name")
    args = request.get("arguments", {})

    if tool == "parse_gemma4_output":
        raw_output = args.get("output")
        if not raw_output:
            return {"error": "Missing 'output' argument."}
        
        parsed = intercept_gemma4_tool_call(raw_output)
        return {"content": [{"type": "text", "text": parsed}]}
        
    else:
        return {"error": f"Unknown tool: {tool}"}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--describe":
        print(json.dumps({
            "tools": [
                {
                    "name": "parse_gemma4_output",
                    "description": "Extracts JSON tool-calls from Gemma 4 native tags or raw output, bypassing common parsing hallucinations.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "output": {"type": "string", "description": "The raw string output from the Gemma 4 model."}
                        },
                        "required": ["output"]
                    }
                }
            ]
        }))
        sys.exit(0)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_request(req)
            print(json.dumps(res), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
