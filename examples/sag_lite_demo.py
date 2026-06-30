"""
Demonstration script for SAG-Lite and OKF Export.

This script shows how to:
1. Initialize the SAG-Lite search engine.
2. Perform a search query.
3. Export results to OKF format.
"""

import sys
import os
from pathlib import Path

# Add src to path for demo purposes
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge import OKFExporter, SAGLite

def main():
    # Configuration
    db_path = ".cache/search_cache.db"
    
    # Check if DB exists, if not, create a dummy one for demo
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}. Creating a demo database...")
        # In a real scenario, you would have a setup script or migration
        # For this demo, we assume the DB structure exists or is created by the app
        print("Please ensure the database is initialized before running this demo.")
        return

    # Initialize SAG-Lite
    print("Initializing SAG-Lite...")
    sag_lite = SAGLite(db_path)
    
    # Perform a search
    print("\n--- Searching for 'AI' ---")
    results = sag_lite.search("AI", tags=["technology"], limit=5)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']}")
        print(f"   Tags: {', '.join(result['tags'])}")
        print(f"   Score: {result.get('score', 'N/A')}")
        print()

    # Export to OKF
    print("Exporting results to OKF format...")
    exporter = OKFExporter(db_path)
    
    # Export specific results to string
    okf_json = exporter.export_to_string(limit=5)
    print("OKF Export (first 500 chars):")
    print(okf_json[:500] + "...")
    
    # Export to file
    output_file = "output_okf.json"
    exporter.export_to_file(output_file, limit=5)
    print(f"\nFull export saved to: {output_file}")

if __name__ == "__main__":
    main()