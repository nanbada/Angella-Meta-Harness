#!/usr/bin/env python3
"""
MCP Server for Google Scion Coordination.
Provides tools for Angella agents to broadcast findings and query peers
within a Scion Grove.
"""
import json
import os
import sys

def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    tool = request.get("name")
    args = request.get("arguments", {})
    
    # In a real Scion environment, this would interface with the Scion Hub API
    # or the `.scion/coordination` shared directory.
    scion_shared_dir = os.environ.get("SCION_SHARED_DIR", ".scion/shared")

    if tool == "scion_broadcast":
        message = args.get("message")
        agent_id = os.environ.get("SCION_AGENT_ID", "angella-unknown")
        if not message:
            return {"error": "Missing 'message' argument."}
        
        # Simulating broadcast to Scion Hub
        print(f"[SCION BROADCAST from {agent_id}] {message}", file=sys.stderr)
        return {"content": [{"type": "text", "text": f"Successfully broadcasted to Scion Hub: {message}"}]}
        
    elif tool == "scion_query_peers":
        query = args.get("query")
        if not query:
            return {"error": "Missing 'query' argument."}
        
        # Simulating querying other agents in the Scion Grove
        print(f"[SCION QUERY] {query}", file=sys.stderr)
        # Mock response for the experimental integration phase
        mock_response = "Peer Angella-Beta is currently modifying 'src/frontend'. Avoid conflicting changes in that directory."
        return {"content": [{"type": "text", "text": mock_response}]}
        
    else:
        return {"error": f"Unknown tool: {tool}"}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--describe":
        print(json.dumps({
            "tools": [
                {
                    "name": "scion_broadcast",
                    "description": "Broadcasts a discovery, negative memory, or plan to other Angella instances orchestrated by Scion.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "The message or finding to broadcast."}
                        },
                        "required": ["message"]
                    }
                },
                {
                    "name": "scion_query_peers",
                    "description": "Queries the Scion Hub to check what other agents are currently working on to avoid file conflicts or duplicate work.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The question to ask the Scion Hub about peer agents."}
                        },
                        "required": ["query"]
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
