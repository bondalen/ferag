#!/usr/bin/env python3
"""One-off: SELECT upload_cycles for rag_id=26 (source_content length)."""
import os
from pathlib import Path

# Load DATABASE_URL from code/backend/.env if present
env_path = Path(__file__).resolve().parent.parent / "code" / "backend" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.strip().startswith("DATABASE_URL="):
            _, v = line.split("=", 1)
            os.environ["DATABASE_URL"] = v.strip().strip('"').strip("'")
            break

url = os.environ.get("DATABASE_URL", "postgresql://ferag:ferag2026@localhost:45432/ferag_app")
from sqlalchemy import create_engine, text

engine = create_engine(url)
with engine.connect() as conn:
    r = conn.execute(
        text(
            "SELECT id, rag_id, cycle_n, length(source_content) AS len "
            "FROM upload_cycles WHERE rag_id = 26 ORDER BY id DESC LIMIT 5"
        )
    )
    for row in r:
        print(row)
