#!/usr/bin/env python3
import sqlite3
import os
from pathlib import Path
import re

def _knowledge_dir() -> Path:
    return Path(os.environ.get("ANGELLA_ROOT", os.getcwd())).resolve() / "knowledge"

def _db_path() -> Path:
    db_dir = Path(os.environ.get("ANGELLA_ROOT", os.getcwd())).resolve() / ".angella" / "graph"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "knowledge.db"

def init_db():
    conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts 
        USING fts5(path, title, content, tokenize='porter')
    """)
    conn.commit()
    conn.close()

def _extract_title(content: str, filename: str) -> str:
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return filename

def build_index():
    init_db()
    k_dir = _knowledge_dir()
    if not k_dir.exists():
        return
    
    conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge_fts")
    
    count = 0
    for root, _, files in os.walk(k_dir):
        for f in files:
            if f.endswith(".md"):
                path = Path(root) / f
                rel_path = str(path.relative_to(k_dir))
                try:
                    content = path.read_text(encoding='utf-8')
                    title = _extract_title(content, f)
                    cursor.execute(
                        "INSERT INTO knowledge_fts (path, title, content) VALUES (?, ?, ?)",
                        (rel_path, title, content)
                    )
                    count += 1
                except Exception as e:
                    print(f"Error reading {rel_path}: {e}")
                    
    conn.commit()
    conn.close()
    return count

def query_index(query: str, limit: int = 3):
    init_db()
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Simple FTS5 query: Convert query to OR terms to be more forgiving, or just exact match
    # A robust approach: match ANY of the words
    clean_query = re.sub(r'[^a-zA-Z0-9\s]', ' ', query).strip()
    fts_query = ' OR '.join(clean_query.split())
    if not fts_query:
        fts_query = clean_query

    try:
        cursor.execute("""
            SELECT path, title, snippet(knowledge_fts, 2, '>>>', '<<<', '...', 64) as matched_content 
            FROM knowledge_fts 
            WHERE knowledge_fts MATCH ? 
            ORDER BY rank 
            LIMIT ?
        """, (fts_query, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        
        # If no results from FTS, fallback to simple LIKE
        if not results:
            cursor.execute("""
                SELECT path, title, substr(content, 1, 500) || '...' as matched_content 
                FROM knowledge_fts 
                WHERE content LIKE ? OR title LIKE ?
                LIMIT ?
            """, (f'%{query}%', f'%{query}%', limit))
            results = [dict(row) for row in cursor.fetchall()]
            
        return results
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        print(f"Indexed {build_index()} documents.")
    elif len(sys.argv) > 2 and sys.argv[1] == "query":
        print(query_index(sys.argv[2]))
