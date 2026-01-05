import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any


class Database:
    def __init__(self, path: str = "data.db"):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                key TEXT NOT NULL,
                bound_user_id INTEGER,
                bound_username TEXT,
                bound_at TEXT
            )
            """
        )
        self.conn.commit()

    def create_invoice(self, invoice_id: str, key: str) -> bool:
        now = datetime.utcnow().isoformat()
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO invoices (invoice_id, created_at, key) VALUES (?, ?, ?)",
                (invoice_id, now, key),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def bind_invoice(self, invoice_id: str, user_id: int, username: str) -> Dict[str, Any]:
        cur = self.conn.cursor()
        row = cur.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "not_found"}
        if row["bound_user_id"] is not None:
            return {"ok": False, "error": "already_bound", "invoice": dict(row)}
        now = datetime.utcnow().isoformat()
        cur.execute(
            "UPDATE invoices SET bound_user_id = ?, bound_username = ?, bound_at = ? WHERE invoice_id = ?",
            (user_id, username, now, invoice_id),
        )
        self.conn.commit()
        return {"ok": True, "invoice": self.get_invoice(invoice_id)}


db = Database()

if __name__ == "__main__":
    print("DB initialized at data.db")
