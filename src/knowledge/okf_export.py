"""
OKF (Open Knowledge Format) Export Module for MisakaNet.

This module provides functionality to export lessons from the MisakaNet database
into the standardized Open Knowledge Format (OKF).

OKF Schema:
{
    "type": "lesson",
    "title": str,
    "description": str,
    "tags": list[str],
    "timestamp": str (ISO 8601),
    "content": str (optional, full text),
    "source_id": str
}
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

class OKFExporter:
    """Handles exporting MisakaNet lessons to OKF standard."""
    
    OKF_SCHEMA_VERSION = "1.0.0"
    
    def __init__(self, db_path: str):
        """
        Initialize the exporter with a path to the MisakaNet SQLite database.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._validate_db()

    def _validate_db(self) -> None:
        """Validate that the database exists and has the expected structure."""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check for expected tables (assuming 'lessons' table exists based on context)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lessons';")
        if not cursor.fetchone():
            raise ValueError("Database missing 'lessons' table. Expected schema not found.")
        
        conn.close()

    def _fetch_lessons(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch lessons from the database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM lessons ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def to_okf(self, lessons: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Convert internal lesson objects to OKF format.
        
        Args:
            lessons: Optional list of lesson dicts. If None, fetches from DB.
            
        Returns:
            List of dictionaries conforming to OKF schema.
        """
        if lessons is None:
            lessons = self._fetch_lessons()
            
        okf_lessons = []
        
        for lesson in lessons:
            # Map internal fields to OKF standard fields
            okf_entry = {
                "type": "lesson",
                "title": lesson.get("title", "Untitled Lesson"),
                "description": lesson.get("description", ""),
                "tags": lesson.get("tags", []) if isinstance(lesson.get("tags"), list) else [],
                "timestamp": lesson.get("created_at", datetime.now().isoformat()),
                "source_id": str(lesson.get("id", "")),
                "content": lesson.get("content", ""), # Optional full content
                "metadata": {
                    "format_version": self.OKF_SCHEMA_VERSION,
                    "exported_at": datetime.now().isoformat()
                }
            }
            okf_lessons.append(okf_entry)
            
        return okf_lessons

    def export_to_file(self, output_path: str, limit: Optional[int] = None) -> str:
        """
        Export lessons to a JSON file in OKF format.
        
        Args:
            output_path: Path to the output JSON file.
            limit: Optional limit on number of lessons to export.
            
        Returns:
            Path to the created file.
        """
        okf_data = self.to_okf(limit=limit)
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(okf_data, f, indent=2, ensure_ascii=False)
            
        return str(output_file)

    def export_to_string(self, limit: Optional[int] = None) -> str:
        """
        Export lessons to a JSON string in OKF format.
        
        Args:
            limit: Optional limit on number of lessons to export.
            
        Returns:
            JSON string representation of OKF data.
        """
        okf_data = self.to_okf(limit=limit)
        return json.dumps(okf_data, indent=2, ensure_ascii=False)