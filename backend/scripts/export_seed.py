"""
Export current SQLite data to seed files for offline/first-run use.

Usage:
    cd backend
    python scripts/export_seed.py

Outputs:
    seed/prompts.csv          - all prompts rows
    seed/analysis_results.json - all analysis_results rows (language, topics, etc.)
"""

import csv
import json
import os
import sqlite3
import sys

# Allow running from backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings

SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed")
PROMPTS_CSV = os.path.join(SEED_DIR, "prompts.csv")
ANALYSIS_JSON = os.path.join(SEED_DIR, "analysis_results.json")


def export():
    os.makedirs(SEED_DIR, exist_ok=True)
    conn = sqlite3.connect(settings.cache_db_path)
    conn.row_factory = sqlite3.Row

    # --- Export prompts ---
    rows = conn.execute("SELECT * FROM prompts").fetchall()
    if rows:
        cols = rows[0].keys()
        with open(PROMPTS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows([dict(r) for r in rows])
        print(f"Exported {len(rows):,} prompts → {PROMPTS_CSV}")
    else:
        print("No prompts to export.")

    # --- Export analysis_results (latest per type) ---
    result_rows = conn.execute("""
        SELECT result_type, result_json
        FROM analysis_results
        WHERE id IN (
            SELECT MAX(id) FROM analysis_results GROUP BY result_type
        )
    """).fetchall()

    analysis = {}
    for row in result_rows:
        try:
            analysis[row["result_type"]] = json.loads(row["result_json"])
        except Exception:
            pass

    with open(ANALYSIS_JSON, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False)
    print(f"Exported {len(analysis)} analysis result types → {ANALYSIS_JSON}")

    conn.close()


if __name__ == "__main__":
    export()
