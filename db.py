import sqlite3
from datetime import datetime

conn = sqlite3.connect("invoices.db", check_same_thread=False)
c = conn.cursor()

# Create table
c.execute("""CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    key TEXT,
    bound_user TEXT,
    bound_at TEXT,
    created_at TEXT
)""")
conn.commit()


class DB:

    def create_invoice(self, invoice_id, key):
        c.execute("SELECT * FROM invoices WHERE invoice_id=?", (invoice_id, ))
        if c.fetchone():
            return False
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO invoices VALUES (?, ?, ?, ?, ?)",
                  (invoice_id, key, None, None, now))
        conn.commit()
        return True

    def bind_invoice(self, invoice_id, user_id, username):
        c.execute("SELECT * FROM invoices WHERE invoice_id=?", (invoice_id, ))
        row = c.fetchone()
        if not row:
            return {"ok": False, "error": "not_found"}
        if row[2]:
            return {
                "ok": False,
                "error": "already_bound",
                "invoice": {
                    "bound_username": row[2],
                    "bound_at": row[3]
                }
            }
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "UPDATE invoices SET bound_user=?, bound_at=? WHERE invoice_id=?",
            (username, now, invoice_id))
        conn.commit()
        return {
            "ok": True,
            "invoice": {
                "invoice_id": invoice_id,
                "bound_username": username,
                "bound_at": now,
                "key": row[1],
                "created_at": row[4]
            }
        }

    def get_invoice(self, invoice_id):
        c.execute("SELECT * FROM invoices WHERE invoice_id=?", (invoice_id, ))
        row = c.fetchone()
        if not row:
            return None
        return {
            "invoice_id": row[0],
            "key": row[1],
            "bound_username": row[2],
            "bound_at": row[3],
            "created_at": row[4]
        }

    def delete_invoice(self, invoice_id):
        c.execute("DELETE FROM invoices WHERE invoice_id=?", (invoice_id, ))
        conn.commit()
        return c.rowcount > 0

    def update_invoice(self, invoice_id, key):
        c.execute("UPDATE invoices SET key=? WHERE invoice_id=?",
                  (key, invoice_id))
        conn.commit()
        return c.rowcount > 0

    def list_invoices(self):
        c.execute("SELECT * FROM invoices")
        return c.fetchall()


db = DB()
