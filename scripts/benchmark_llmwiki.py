#!/usr/bin/env python3
import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp-servers'))
import llmwiki_compiler_ops

def run_benchmark():
    # Let's test the overhead of the npx llmwiki query
    start_time = time.perf_counter()
    iterations = 3
    for _ in range(iterations):
        result = llmwiki_compiler_ops.handle_request({
            "type": "call_tool",
            "name": "llmwiki_query",
            "arguments": {"question": "What is the ratcheting pattern?"}
        })
    end_time = time.perf_counter()
    
    avg_time = (end_time - start_time) / iterations
    print(f"Average time per llmwiki_query (npx) call: {avg_time:.4f} seconds")
    return avg_time

if __name__ == "__main__":
    run_benchmark()
