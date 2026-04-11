#!/usr/bin/env python3
"""
Angella Graph Watchdog
Background process to pre-compute and update the code graph upfront.
Uses file system events to trigger incremental indexing.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Try to import watchdog, if not available, we can use a simple poll or notify user
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Watchdog library not found. Please install it: pip install watchdog")
    Observer = None
    FileSystemEventHandler = object

def _angella_root() -> Path:
    return Path(os.environ.get("ANGELLA_ROOT", os.getcwd())).resolve()

class CodeGraphHandler(FileSystemEventHandler):
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.last_run = 0
        self.debounce_seconds = 2

    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Code Graph (Python)
        if event.src_path.endswith(".py"):
            self._trigger_code_index(event.src_path)
            
        # Knowledge Base (Markdown)
        elif event.src_path.endswith(".md") and "knowledge" in str(Path(event.src_path).resolve()):
            self._trigger_knowledge_index(event.src_path)

    def _trigger_code_index(self, file_path: str):
        now = time.time()
        if now - self.last_run < self.debounce_seconds:
            return
        
        rel_path = os.path.relpath(file_path, self.root_dir)
        print(f"[Watchdog] Code change detected: {rel_path}. Re-indexing code graph...")
        
        try:
            subprocess.run(["python3", "mcp-servers/code_graph_ops.py", "index", "--auto", rel_path], check=False, capture_output=True)
        except Exception as e:
            print(f"[Watchdog] Code indexing failed: {e}")
            
        self.last_run = now

    def _trigger_knowledge_index(self, file_path: str):
        now = time.time()
        # Separate debounce for knowledge to avoid colliding with code
        if not hasattr(self, 'last_knowledge_run'):
            self.last_knowledge_run = 0
            
        if now - self.last_knowledge_run < self.debounce_seconds:
            return
        
        rel_path = os.path.relpath(file_path, self.root_dir)
        print(f"[Watchdog] Knowledge change detected: {rel_path}. Re-indexing FTS...")
        
        try:
            subprocess.run(["python3", "mcp-servers/knowledge_index.py", "build"], check=False, capture_output=True)
        except Exception as e:
            print(f"[Watchdog] Knowledge indexing failed: {e}")
            
        self.last_knowledge_run = now

def start_watchdog():
    root = _angella_root()
    print(f"Starting Angella Graph Watchdog on {root}...")
    
    if Observer is None:
        print("Falling back to manual polling (or just exit).")
        return

    event_handler = CodeGraphHandler(root)
    observer = Observer()
    observer.schedule(event_handler, str(root), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_watchdog()
