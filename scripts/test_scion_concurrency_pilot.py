#!/usr/bin/env python3
"""
Pilot test for multi-agent simultaneous execution and hard conflict handling in Scion.
This script spawns actual concurrent processes to verify file-backed coordination.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
SCION_OPS = ROOT_DIR / "mcp-servers" / "scion_coordination_ops.py"

def run_scion_tool(shared_dir: Path, agent_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    env = os.environ.copy()
    env["SCION_SHARED_DIR"] = str(shared_dir)
    env["SCION_AGENT_ID"] = agent_id
    env["SCION_TTL_SECONDS"] = "30"
    
    input_data = json.dumps({"type": "call_tool", "name": tool_name, "arguments": arguments})
    result = subprocess.run(
        [sys.executable, str(SCION_OPS)],
        input=input_data,
        capture_output=True,
        text=True,
        env=env,
        check=True
    )
    return json.loads(result.stdout)

def agent_a_logic(shared_dir: Path):
    agent_id = "agent-alpha"
    print(f"[{agent_id}] Starting...")
    
    # 1. Claim a broad area
    res = run_scion_tool(shared_dir, agent_id, "scion_claim_files", {
        "files": ["src/core"],
        "mode": "exclusive",
        "intent": "Initial setup of core logic"
    })
    print(f"[{agent_id}] Claimed src/core: {res}")
    
    # 2. Simulate work
    time.sleep(3)
    
    # 3. Broadcast progress
    run_scion_tool(shared_dir, agent_id, "scion_broadcast", {
        "message": "Core setup halfway done. Sub-area src/core/utils is ready for takeover."
    })
    print(f"[{agent_id}] Broadcasted progress.")
    
    # 4. Wait for B to take over (simulated by sleeping or checking state)
    # In a real scenario, A might keep working on other parts.
    time.sleep(5)
    
    # 5. Release remaining
    run_scion_tool(shared_dir, agent_id, "scion_release_claims", {"files": ["src/core"]})
    print(f"[{agent_id}] Released src/core.")

def agent_b_logic(shared_dir: Path):
    agent_id = "agent-beta"
    print(f"[{agent_id}] Starting...")
    time.sleep(1) # Start slightly later
    
    # 1. Try to claim something overlapping - should fail (Hard Conflict)
    res = run_scion_tool(shared_dir, agent_id, "scion_claim_files", {
        "files": ["src/core/logic.py"],
        "mode": "exclusive"
    })
    if "error" in res:
        print(f"[{agent_id}] Expected conflict: {res['error']}")
    else:
        print(f"[{agent_id}] Unexpected success in exclusive claim: {res}")
    
    # 2. Wait for A's broadcast (polled via inspect_state in real life, here we just wait)
    time.sleep(3)
    
    # 3. Perform takeover of a sub-path
    res = run_scion_tool(shared_dir, agent_id, "scion_claim_files", {
        "files": ["src/core/utils.py"],
        "mode": "takeover",
        "takeover_from": "agent-alpha",
        "intent": "Implementing low-level utils"
    })
    print(f"[{agent_id}] Takeover result: {res}")
    
    # 4. Do work
    time.sleep(2)
    
    # 5. Release
    run_scion_tool(shared_dir, agent_id, "scion_release_claims", {"files": ["src/core/utils.py"]})
    print(f"[{agent_id}] Released src/core/utils.py.")

def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        shared_dir = Path(tmp_dir) / "scion-shared"
        shared_dir.mkdir()
        
        print(f"Pilot test shared dir: {shared_dir}")
        
        # We use separate processes for Alpha and Beta
        # To make it easier to see logs, we'll run them in the background via subprocess
        
        def run_agent(target_func):
            # We'll just call the functions directly in this script but using different agent_ids
            # To simulate real concurrency, we should use multiprocessing or separate scripts.
            # Let's use multiprocessing.
            from multiprocessing import Process
            p = Process(target=target_func, args=(shared_dir,))
            return p

        p_alpha = run_agent(agent_a_logic)
        p_beta = run_agent(agent_b_logic)
        
        p_alpha.start()
        p_beta.start()
        
        p_alpha.join()
        p_beta.join()
        
        # Verify final state
        res = run_scion_tool(shared_dir, "monitor", "scion_inspect_state", {})
        print("\nFinal Scion State:")
        print(res["content"][0]["text"])
        
        # Basic assertions on the output would be here in a real test
        # For now, we manually verify the log sequence.

if __name__ == "__main__":
    main()
