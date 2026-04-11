#!/usr/bin/env python3
import time
import sys
import os
import shutil
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp-servers'))
import scion_coordination_ops

def run_benchmark():
    # Setup temp shared dir for scion
    temp_shared = Path("telemetry/tmp_scion_shared")
    if temp_shared.exists():
        shutil.rmtree(temp_shared)
    temp_shared.mkdir(parents=True, exist_ok=True)
    
    os.environ.setdefault("SCION_BACKEND", "sqlite")
    os.environ["SCION_SHARED_DIR"] = str(temp_shared)
    
    provider = scion_coordination_ops.get_provider()
    backend_name = provider.__class__.__name__

    # Pre-populate some claims
    for i in range(100):
        provider.claim_files(f"agent-{i}", [f"file_{i}.py"], "advisory", "", "", None, "", {})

    # Measure time for a new claim with 100 existing ones
    start_time = time.perf_counter()
    iterations = 50
    for i in range(iterations):
        provider.claim_files("main-agent", [f"new_file_{i}.py"], "exclusive", "test", "msg", None, "", {})
    end_time = time.perf_counter()

    avg_time = (end_time - start_time) / iterations
    print(f"Average time per claim_files ({backend_name}) with 100 peers: {avg_time:.4f} seconds")

    
    # Cleanup
    shutil.rmtree(temp_shared)
    return avg_time

if __name__ == "__main__":
    run_benchmark()
