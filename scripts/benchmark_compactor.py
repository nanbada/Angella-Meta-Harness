#!/usr/bin/env python3
import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp-servers'))
import output_compactor

# Generate a large dummy payload mimicking git status or test output
def generate_payload(lines_count):
    payload = []
    for i in range(lines_count):
        if i % 10 == 0:
            payload.append(f"error: test failed at line {i}")
        elif i % 5 == 0:
            payload.append(f"src/module/file_{i}.py")
        elif i % 2 == 0:
            payload.append("  ") # noise
        else:
            payload.append(f"INFO: doing some work step {i}")
    return "\n".join(payload)

def run_benchmark():
    payload = generate_payload(50000)
    
    start_time = time.perf_counter()
    # Run multiple times to get a stable average
    iterations = 5
    for _ in range(iterations):
        result = output_compactor.compact_output("test_output", payload, budget_chars=2000)
    end_time = time.perf_counter()
    
    avg_time = (end_time - start_time) / iterations
    print(f"Average time per compact_output call: {avg_time:.4f} seconds")
    return avg_time

if __name__ == "__main__":
    run_benchmark()
