#!/usr/bin/env python3
"""JobTrail local API server.

A dependency-free Python HTTP server that stores job applications in a
small SQLite database and serves the static frontend.

Endpoints:
    GET    /api/jobs         list all applications (newest first)
    POST   /api/jobs         create an application
    PATCH  /api/jobs/<id>    update an application's stage
    DELETE /api/jobs/<id>    remove an application

Usage:
    python3 server.py [port]     # default port: 8000
"""

import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import date, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "jobtrail.db"

STAGES = ["Applied", "Screening", "Interview", "Offer", "Rejected"]


def days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


SEED = [
    ("a1", "Northstar Labs", "Frontend Engineer", "Interview", "Prepare a product walkthrough", days_ago(7)),
    ("a2", "Fieldnote", "Product Engineer", "Screening", "Reply to recruiter", days_ago(9)),
    ("a3", "Kindred Systems", "Web Developer", "Applied", "Check back next week", days_ago(13)),
    ("a4", "Lumen Works", "UI Engineer", "Offer", "Review offer details", days_ago(16)),
]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id        TEXT PRIMARY KEY,
                company   TEXT NOT NULL,
                role      TEXT NOT NULL,
                stage     TEXT NOT NULL,
                next_step TEXT NOT NULL DEFAULT '',
                date      TEXT NOT NULL
            )
            """
        )
        if conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO jobs (id, company, role, stage, next_step, date) VALUES (?, ?, ?, ?, ?, ?)",
                SEED,
            )


def row_to_job(row):
    return {
        "id": row["id"],
        "company": row["company"],
        "role": row["role"],
        "stage": row["stage"],
        "nextStep": row["next_step"],
        "date": row["date"],
    }


class JobTrailHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/jobs":
            with connect() as conn:
                rows = conn.execute("SELECT * FROM jobs ORDER BY date DESC, rowid DESC").fetchall()
            self.send_json({"jobs": [row_to_job(r) for r in rows]})
        elif path.startswith("/api/"):
            self.send_json({"error": "Not found"}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/jobs":
            return self.send_json({"error": "Not found"}, 404)
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "Invalid JSON body"}, 400)

        company = str(data.get("company") or "").strip()
        role = str(data.get("role") or "").strip()
        stage = str(data.get("stage") or "Applied").strip()
        next_step = str(data.get("nextStep") or "").strip()

        if not company or not role:
            return self.send_json({"error": "Company and role are required"}, 400)
        if stage not in STAGES:
            return self.send_json({"error": "Unknown stage: %s" % stage}, 400)

        job = {
            "id": str(uuid.uuid4()),
            "company": company[:70],
            "role": role[:90],
            "stage": stage,
            "nextStep": next_step[:120],
            "date": date.today().isoformat(),
        }
        with connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, company, role, stage, next_step, date) VALUES (?, ?, ?, ?, ?, ?)",
                (job["id"], job["company"], job["role"], job["stage"], job["nextStep"], job["date"]),
            )
        self.send_json(job, 201)

    def do_PATCH(self):
        match = re.fullmatch(r"/api/jobs/([^/]+)", urlparse(self.path).path)
        if not match:
            return self.send_json({"error": "Not found"}, 404)
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "Invalid JSON body"}, 400)
        stage = str(data.get("stage") or "").strip()
        if stage not in STAGES:
            return self.send_json({"error": "Unknown stage: %s" % stage}, 400)

        job_id = match.group(1)
        with connect() as conn:
            cur = conn.execute("UPDATE jobs SET stage = ? WHERE id = ?", (stage, job_id))
            if cur.rowcount == 0:
                return self.send_json({"error": "Application not found"}, 404)
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.send_json(row_to_job(row))

    def do_DELETE(self):
        match = re.fullmatch(r"/api/jobs/([^/]+)", urlparse(self.path).path)
        if not match:
            return self.send_json({"error": "Not found"}, 404)
        job_id = match.group(1)
        with connect() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            if cur.rowcount == 0:
                return self.send_json({"error": "Application not found"}, 404)
        self.send_json({"ok": True})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    init_db()
    os.chdir(ROOT)
    server = HTTPServer(("127.0.0.1", port), JobTrailHandler)
    print("JobTrail running at http://localhost:%d  (SQLite: %s)" % (port, DB_PATH.name))
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
