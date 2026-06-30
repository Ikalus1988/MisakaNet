"""
SAG-Lite (SQLite-backed Agent Knowledge) Search Module.

SAG-Lite provides a lightweight, SQLite-based search engine specifically
optimized for MisakaNet's knowledge base. Unlike generic RAG, SAG-Lite
focuses on structured metadata filtering combined with full-text search.

Key Features:
- SQLite Full-Text Search (FTS5) integration
- Tag-based filtering
- Timestamp range queries
- OKF-compatible result formatting
"""

import sqlite3
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

class SAGLite:
    """
    SAG-Lite Search Engine.
    
    Uses SQLite FTS5 for high-performance text search and standard 
    SQL for metadata filtering.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize SAG-Lite with the database path.
        
        Args:
            db_path: Path to the SQLite database.
        """
        self.db_path = db_path
        self._ensure_fts_index()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_fts_index(self) -> None:
        """
        Ensure the FTS5 virtual table exists for the 'lessons' table.
        If not, create it and populate it.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if FTS table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lessons_fts';")
        if not cursor.fetchone():
            # Create FTS5 table
            cursor.execute("""
                CREATE VIRTUAL TABLE lessons_fts USING fts5(
                    title,
                    description,
                    content,
                    content='lessons',
                    content_rowid='id'
                );
            """)
            
            # Populate FTS table
            cursor.execute("""
                INSERT INTO lessons_fts(lessons_fts) VALUES('rebuild');
            """)
            
            # Create trigger to keep FTS in sync (simplified for this implementation)
            # In a production environment, you might want to handle updates/deletes explicitly
            # or use a background job to sync.
            
        conn.commit()
        conn.close()

    def search(
        self, 
        query: str, 
        tags: Optional[List[str]] = None, 
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Perform a search using SAG-Lite.
        
        Args:
            query: Full-text search query string.
            tags: Optional list of tags to filter by.
            limit: Maximum number of results.
            offset: Pagination offset.
            
        Returns:
            List of matching lessons in OKF-compatible format.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Base query using FTS5
        # Note: FTS5 syntax requires quoting for phrases
        fts_query = query
        
        # Build SQL
        sql = """
            SELECT l.id, l.title, l.description, l.tags, l.created_at, l.content
            FROM lessons l
            JOIN lessons_fts fts ON l.id = fts.rowid
            WHERE fts MATCH ?
        """
        params = [fts_query]
        
        # Add tag filtering if provided
        if tags:
            # Assuming tags are stored as JSON array or comma-separated string
            # This is a simplified check; production might need JSON extraction
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("l.tags LIKE ?")
                params.append(f'%{tag}%')
            
            sql += f" AND {' AND '.join(tag_conditions)}"
        
        # Add ordering and pagination
        sql += " ORDER BY rank DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            # Format as OKF-compatible dict
            result = {
                "type": "lesson",
                "title": row["title"],
                "description": row["description"],
                "tags": row["tags"] if isinstance(row["tags"], list) else [],
                "timestamp": row["created_at"],
                "source_id": str(row["id"]),
                "content": row["content"],
                "score": row.get("rank", 0) # FTS rank
            }
            results.append(result)
            
        return results

    def get_by_id(self, lesson_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific lesson by ID.
        
        Args:
            lesson_id: The ID of the lesson.
            
        Returns:
            Lesson dict or None.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        return {
            "type": "lesson",
            "title": row["title"],
            "description": row["description"],
            "tags": row["tags"] if isinstance(row["tags"], list) else [],
            "timestamp": row["created_at"],
            "source_id": str(row["id"]),
            "content": row["content"]
        }

    def get_all_tags(self) -> List[str]:
        """
        Retrieve all unique tags from the database.
        
        Returns:
            List of unique tag strings.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Assuming tags are stored as a JSON array string or comma-separated
        # This is a simplified extraction
        cursor.execute("SELECT tags FROM lessons")
        rows = cursor.fetchall()
        conn.close()
        
        all_tags = set()
        for row in rows:
            tags_str = row["tags"]
            if isinstance(tags_str, list):
                all_tags.update(tags_str)
            elif isinstance(tags_str, str):
                # Handle comma-separated or JSON string
                try:
                    import json
                    tags_list = json.loads(tags_str)
                    if isinstance(tags_list, list):
                        all_tags.update(tags_list)
                    else:
                        all_tags.add(tags_str)
                except:
                    # Fallback for comma-separated
                    all_tags.update([t.strip() for t in tags_str.split(',') if t.strip()])
                    
        return sorted(list(all_tags))