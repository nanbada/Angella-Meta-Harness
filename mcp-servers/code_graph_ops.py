#!/usr/bin/env python3
"""
MCP Server for Code Relationship Graph (SQLite-based).
Inspired by tirth8205/code-review-graph.
Provides AST-based indexing and blast radius analysis.
"""

import sqlite3
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Configuration ---

def _angella_root() -> Path:
    return Path(os.environ.get("ANGELLA_ROOT", os.getcwd())).resolve()

def _db_path() -> Path:
    db_dir = _angella_root() / ".angella" / "graph"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "code_graph.db"

# --- Database Setup ---

def init_db():
    conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()
    
    # Files table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE,
        last_indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Symbols table (Functions, Classes, etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS symbols (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER,
        name TEXT,
        kind TEXT, -- function, class, variable
        start_line INTEGER,
        end_line INTEGER,
        FOREIGN KEY(file_id) REFERENCES files(id)
    )
    """)
    
    # Relationships table (Calls, Inheritance, Imports)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_symbol_id INTEGER,
        to_symbol_id INTEGER,
        kind TEXT, -- calls, inherits, imports
        FOREIGN KEY(from_symbol_id) REFERENCES symbols(id),
        FOREIGN KEY(to_symbol_id) REFERENCES symbols(id)
    )
    """)
    
    conn.commit()
    conn.close()

# --- Tool Implementations ---

def index_file(file_path: str, symbols: List[Dict[str, Any]], relationships: List[Dict[str, Any]]):
    """
    Index a file's symbols and relationships.
    Expected symbols format: [{'name': 'foo', 'kind': 'function', 'start_line': 10, 'end_line': 20}, ...]
    Expected relationships format: [{'from_symbol_name': 'foo', 'to_symbol_name': 'bar', 'kind': 'calls'}, ...]
    """
    conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()
    
    try:
        # Upsert file
        cursor.execute("INSERT OR REPLACE INTO files (path, last_indexed_at) VALUES (?, CURRENT_TIMESTAMP)", (file_path,))
        file_id = cursor.lastrowid or cursor.execute("SELECT id FROM files WHERE path = ?", (file_path,)).fetchone()[0]
        
        # Clear old symbols for this file
        cursor.execute("DELETE FROM relationships WHERE from_symbol_id IN (SELECT id FROM symbols WHERE file_id = ?)", (file_id,))
        cursor.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
        
        # Insert new symbols
        symbol_map = {}
        for s in symbols:
            cursor.execute("INSERT INTO symbols (file_id, name, kind, start_line, end_line) VALUES (?, ?, ?, ?, ?)",
                           (file_id, s['name'], s['kind'], s.get('start_line'), s.get('end_line')))
            symbol_map[s['name']] = cursor.lastrowid
            
        # Insert relationships (simplified: assuming names are unique enough for this demo/MVP)
        for r in relationships:
            from_id = symbol_map.get(r['from_symbol_name'])
            # 'to' symbol might be in another file, need to look up
            cursor.execute("SELECT id FROM symbols WHERE name = ? LIMIT 1", (r['to_symbol_name'],))
            res = cursor.fetchone()
            if from_id and res:
                cursor.execute("INSERT INTO relationships (from_symbol_id, to_symbol_id, kind) VALUES (?, ?, ?)",
                               (from_id, res[0], r['kind']))
        
        conn.commit()
        return {"status": "success", "file_path": file_path, "symbols_indexed": len(symbols)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

def get_blast_radius(symbol_name: str, depth: int = 2) -> Dict[str, Any]:
    """
    Find symbols that call or depend on the given symbol (Upstream analysis).
    """
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Find the starting symbol
        cursor.execute("SELECT id, name, file_id FROM symbols WHERE name = ? LIMIT 1", (symbol_name,))
        start_symbol = cursor.fetchone()
        if not start_symbol:
            return {"status": "error", "message": f"Symbol '{symbol_name}' not found."}
        
        affected_symbols = []
        to_process = [(start_symbol['id'], 0)]
        visited = {start_symbol['id']}
        
        while to_process:
            curr_id, curr_depth = to_process.pop(0)
            if curr_depth >= depth:
                continue
            
            # Find callers (Who calls me?)
            cursor.execute("""
                SELECT s.id, s.name, s.kind, f.path as file_path 
                FROM symbols s
                JOIN relationships r ON s.id = r.from_symbol_id
                JOIN files f ON s.file_id = f.id
                WHERE r.to_symbol_id = ?
            """, (curr_id,))
            
            for row in cursor.fetchall():
                if row['id'] not in visited:
                    visited.add(row['id'])
                    affected_symbols.append(dict(row))
                    to_process.append((row['id'], curr_depth + 1))
        
        return {
            "symbol": symbol_name,
            "depth": depth,
            "affected_count": len(affected_symbols),
            "affected_symbols": affected_symbols
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

import ast

def _extract_python_symbols(file_content: str) -> List[Dict[str, Any]]:
    symbols = []
    try:
        tree = ast.parse(file_content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append({
                    "name": node.name,
                    "kind": "function",
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno)
                })
            elif isinstance(node, ast.ClassDef):
                symbols.append({
                    "name": node.name,
                    "kind": "class",
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno)
                })
    except:
        pass
    return symbols

def _extract_python_relationships(file_content: str) -> List[Dict[str, Any]]:
    relationships = []
    try:
        tree = ast.parse(file_content)
        current_func = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                current_func = node.name
            
            if isinstance(node, ast.Call) and current_func:
                if isinstance(node.func, ast.Name):
                    relationships.append({
                        "from_symbol_name": current_func,
                        "to_symbol_name": node.func.id,
                        "kind": "calls"
                    })
                elif isinstance(node.func, ast.Attribute):
                    relationships.append({
                        "from_symbol_name": current_func,
                        "to_symbol_name": node.func.attr,
                        "kind": "calls"
                    })
    except:
        pass
    return relationships

def auto_index_file(file_path: str):
    """
    Automatically parse and index a file based on its extension.
    """
    path = _angella_root() / file_path
    if not path.exists():
        return {"status": "error", "message": f"File {file_path} not found."}
    
    content = path.read_text(encoding="utf-8")
    symbols = []
    relationships = []
    
    if file_path.endswith(".py"):
        symbols = _extract_python_symbols(content)
        relationships = _extract_python_relationships(content)
    # Add other languages here...
    
    return index_file(file_path, symbols, relationships)

# --- Handler Update ---

def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    tool = request.get("name")
    args = request.get("arguments", {})

    if tool == "code_graph_index":
        if args.get("auto", True):
            return auto_index_file(args.get("file_path"))
        return index_file(args.get("file_path"), args.get("symbols", []), args.get("relationships", []))
    if tool == "code_graph_blast_radius":
        return get_blast_radius(args.get("symbol_name"), args.get("depth", 2))
    
    return {"error": f"Unknown tool: {tool}"}

if __name__ == "__main__":
    init_db()
    for line in sys.stdin:
        try:
            req = json.loads(line.strip())
            print(json.dumps(handle_request(req)), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
