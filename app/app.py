import os
import sqlite3
import logging
import re
from flask import Flask, request, jsonify, g
 
# ---------------------------------------------------------------------------
# Configuration via environment variables
# ---------------------------------------------------------------------------
DB_PATH = os.environ.get("DATABASE_PATH", "/data/app.db")
PORT = int(os.environ.get("PORT", 5000))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
 
# ---------------------------------------------------------------------------
# Logging setup — logs go to stdout so `docker logs` captures them
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("userapi")
 
app = Flask(__name__)
 
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_STATUSES = {"active", "inactive", "pending"}
 
 
def get_db():
    """Get (or create) a per-request DB connection."""
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db
 
 
@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
 
 
def init_db():
    """Create table and seed sample data if the DB doesn't already have it."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active'
        )
        """
    )
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        logger.info("Seeding sample data...")
        seed_rows = [
            ("Ali Khan", "ali.khan@example.com", "active"),
            ("Sara Ahmed", "sara.ahmed@example.com", "active"),
            ("Bilal Raza", "bilal.raza@example.com", "inactive"),
            ("Ayesha Noor", "ayesha.noor@example.com", "pending"),
            ("Hamza Tariq", "hamza.tariq@example.com", "active"),
            ("Zainab Iqbal", "zainab.iqbal@example.com", "inactive"),
            ("Usman Farooq", "usman.farooq@example.com", "active"),
            ("Mahnoor Sheikh", "mahnoor.sheikh@example.com", "pending"),
            # Deliberately tricky rows for negative/edge-case testing:
            ("O'Brien Test", "obrien.test@example.com", "active"),      # apostrophe in name -> SQLi-style test
            ("Robert Drop", "robert.droptable@example.com", "active"),  # classic 'Robert'); DROP TABLE' style name reference
        ]
        conn.executemany(
            "INSERT INTO users (name, email, status) VALUES (?, ?, ?)",
            seed_rows,
        )
        conn.commit()
        logger.info(f"Seeded {len(seed_rows)} users.")
    conn.close()
 
 
def row_to_dict(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"], "status": row["status"]}
 
 
# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
 
@app.route("/health", methods=["GET"])
def health():
    """Health check: verifies the app is up AND the DB is reachable."""
    try:
        db = get_db()
        db.execute("SELECT 1")
        return jsonify({"status": "ok", "db": "connected"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "detail": str(e)}), 503
 
 
@app.route("/users", methods=["GET"])
def list_users():
    db = get_db()
    status_filter = request.args.get("status")
    if status_filter:
        rows = db.execute(
            "SELECT * FROM users WHERE status = ?", (status_filter,)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM users").fetchall()
    logger.info(f"GET /users returned {len(rows)} rows (filter={status_filter})")
    return jsonify([row_to_dict(r) for r in rows]), 200
 
 
@app.route("/users/<user_id>", methods=["GET"])
def get_user(user_id):
    if not user_id.isdigit():
        logger.warning(f"GET /users/{user_id} - invalid id format")
        return jsonify({"error": "id must be an integer"}), 400
 
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        logger.info(f"GET /users/{user_id} - not found")
        return jsonify({"error": "user not found"}), 404
    return jsonify(row_to_dict(row)), 200
 
 
@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "request body must be JSON"}), 400
 
    name = data.get("name")
    email = data.get("email")
    status = data.get("status", "active")
 
    if not name or not isinstance(name, str):
        return jsonify({"error": "name is required and must be a string"}), 400
    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "a valid email is required"}), 400
    if status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(VALID_STATUSES)}"}), 400
 
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (name, email, status) VALUES (?, ?, ?)",
            (name, email, status),
        )
        db.commit()
        new_id = cur.lastrowid
        logger.info(f"POST /users - created id={new_id}")
        row = db.execute("SELECT * FROM users WHERE id = ?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except sqlite3.IntegrityError:
        logger.warning(f"POST /users - duplicate email attempted: {email}")
        return jsonify({"error": "email already exists"}), 409
 
 
@app.route("/users/<user_id>", methods=["PUT"])
def update_user(user_id):
    if not user_id.isdigit():
        return jsonify({"error": "id must be an integer"}), 400
 
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "request body must be JSON"}), 400
 
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return jsonify({"error": "user not found"}), 404
 
    name = data.get("name", row["name"])
    email = data.get("email", row["email"])
    status = data.get("status", row["status"])
 
    if not isinstance(name, str) or not name:
        return jsonify({"error": "name must be a non-empty string"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "a valid email is required"}), 400
    if status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(VALID_STATUSES)}"}), 400
 
    try:
        db.execute(
            "UPDATE users SET name = ?, email = ?, status = ? WHERE id = ?",
            (name, email, status, user_id),
        )
        db.commit()
        logger.info(f"PUT /users/{user_id} - updated")
        updated = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return jsonify(row_to_dict(updated)), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "email already exists"}), 409
 
 
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT)
else:
    # Also init when run under gunicorn (import time)
    init_db()
