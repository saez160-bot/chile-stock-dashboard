"""SQLite database layer for the email app."""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "email_data.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            imap_host TEXT NOT NULL,
            imap_port INTEGER DEFAULT 993,
            smtp_host TEXT NOT NULL,
            smtp_port INTEGER DEFAULT 587,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            use_ssl BOOLEAN DEFAULT 1,
            active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '📁',
            UNIQUE(account_id, name)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            uid TEXT NOT NULL,
            folder TEXT NOT NULL,
            from_addr TEXT,
            from_name TEXT,
            to_addr TEXT,
            cc_addr TEXT,
            subject TEXT,
            preview TEXT,
            body_text TEXT,
            body_html TEXT,
            date TEXT,
            is_read BOOLEAN DEFAULT 0,
            is_starred BOOLEAN DEFAULT 0,
            is_spam BOOLEAN DEFAULT 0,
            has_attachment BOOLEAN DEFAULT 0,
            size_kb INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, uid, folder)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS spam_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type TEXT NOT NULL,
            value TEXT NOT NULL,
            action TEXT DEFAULT 'spam',
            enabled BOOLEAN DEFAULT 1,
            hits INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rule_type, value)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS folder_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            conditions TEXT NOT NULL,
            condition_logic TEXT DEFAULT 'AND',
            actions TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            enabled BOOLEAN DEFAULT 1,
            hits INTEGER DEFAULT 0,
            stop_processing BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ─── Accounts ────────────────────────────────────────────────

def add_account(name, email, imap_host, smtp_host, username, password,
                imap_port=993, smtp_port=587, use_ssl=True):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO accounts
              (name, email, imap_host, imap_port, smtp_host, smtp_port,
               username, password, use_ssl)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (name, email, imap_host, imap_port, smtp_host, smtp_port,
              username, password, use_ssl))
        conn.commit()
        return True, "Cuenta agregada exitosamente"
    except sqlite3.IntegrityError:
        return False, "Ya existe una cuenta con ese correo"
    finally:
        conn.close()


def get_accounts():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM accounts WHERE active=1 ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_account(account_id):
    conn = get_connection()
    conn.execute("UPDATE accounts SET active=0 WHERE id=?", (account_id,))
    conn.commit()
    conn.close()


# ─── Emails ──────────────────────────────────────────────────

def upsert_email(account_id, uid, folder, from_addr, from_name, to_addr,
                 cc_addr, subject, preview, body_text, body_html, date,
                 has_attachment=False, size_kb=0):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO emails
          (account_id, uid, folder, from_addr, from_name, to_addr, cc_addr,
           subject, preview, body_text, body_html, date, has_attachment, size_kb)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (account_id, uid, folder, from_addr, from_name, to_addr, cc_addr,
          subject, preview, body_text, body_html, date, has_attachment, size_kb))
    conn.commit()
    conn.close()


def get_emails(account_id, folder, limit=100, search=""):
    conn = get_connection()
    if search:
        rows = conn.execute("""
            SELECT * FROM emails
            WHERE account_id=? AND folder=?
              AND (from_addr LIKE ? OR from_name LIKE ?
                   OR subject LIKE ? OR preview LIKE ?)
            ORDER BY date DESC LIMIT ?
        """, (account_id, folder,
              f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%",
              limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM emails
            WHERE account_id=? AND folder=?
            ORDER BY date DESC LIMIT ?
        """, (account_id, folder, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_email_by_id(email_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM emails WHERE id=?", (email_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_read(email_id, is_read=True):
    conn = get_connection()
    conn.execute("UPDATE emails SET is_read=? WHERE id=?", (int(is_read), email_id))
    conn.commit()
    conn.close()


def toggle_star(email_id):
    conn = get_connection()
    conn.execute("UPDATE emails SET is_starred=NOT is_starred WHERE id=?", (email_id,))
    conn.commit()
    conn.close()


def move_to_folder(email_id, folder):
    conn = get_connection()
    conn.execute("UPDATE emails SET folder=? WHERE id=?", (folder, email_id))
    conn.commit()
    conn.close()


def delete_email(email_id):
    conn = get_connection()
    # Move to Trash unless already there
    row = conn.execute("SELECT folder FROM emails WHERE id=?", (email_id,)).fetchone()
    if row and row["folder"] != "Trash":
        conn.execute("UPDATE emails SET folder='Trash' WHERE id=?", (email_id,))
    else:
        conn.execute("DELETE FROM emails WHERE id=?", (email_id,))
    conn.commit()
    conn.close()


def get_unread_count(account_id, folder):
    conn = get_connection()
    n = conn.execute("""
        SELECT COUNT(*) FROM emails
        WHERE account_id=? AND folder=? AND is_read=0
    """, (account_id, folder)).fetchone()[0]
    conn.close()
    return n


def get_folder_stats(account_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT folder, COUNT(*) AS total,
               SUM(CASE WHEN is_read=0 THEN 1 ELSE 0 END) AS unread
        FROM emails WHERE account_id=?
        GROUP BY folder
    """, (account_id,)).fetchall()
    conn.close()
    return {r["folder"]: {"total": r["total"], "unread": r["unread"]} for r in rows}


def get_custom_folders(account_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM custom_folders WHERE account_id=? ORDER BY name",
        (account_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_custom_folder(account_id, name, icon="📁"):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO custom_folders (account_id, name, icon) VALUES (?,?,?)",
            (account_id, name, icon)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def delete_custom_folder(folder_id):
    conn = get_connection()
    conn.execute("DELETE FROM custom_folders WHERE id=?", (folder_id,))
    conn.commit()
    conn.close()


# ─── Spam rules ──────────────────────────────────────────────

def get_spam_rules():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM spam_rules ORDER BY rule_type, value"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_spam_rule(rule_type, value, action="spam"):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO spam_rules (rule_type, value, action) VALUES (?,?,?)",
            (rule_type, value.lower().strip(), action)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def toggle_spam_rule(rule_id):
    conn = get_connection()
    conn.execute("UPDATE spam_rules SET enabled=NOT enabled WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


def delete_spam_rule(rule_id):
    conn = get_connection()
    conn.execute("DELETE FROM spam_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


def increment_spam_hits(rule_id):
    conn = get_connection()
    conn.execute("UPDATE spam_rules SET hits=hits+1 WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


# ─── Folder rules ────────────────────────────────────────────

def get_folder_rules():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM folder_rules ORDER BY priority, id"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["conditions"] = json.loads(d["conditions"])
        d["actions"] = json.loads(d["actions"])
        result.append(d)
    return result


def add_folder_rule(name, conditions, actions, condition_logic="AND",
                    priority=0, stop_processing=False):
    conn = get_connection()
    conn.execute("""
        INSERT INTO folder_rules
          (name, conditions, condition_logic, actions, priority, stop_processing)
        VALUES (?,?,?,?,?,?)
    """, (name, json.dumps(conditions), condition_logic,
          json.dumps(actions), priority, int(stop_processing)))
    conn.commit()
    conn.close()


def update_folder_rule(rule_id, name, conditions, actions,
                       condition_logic, priority, enabled, stop_processing):
    conn = get_connection()
    conn.execute("""
        UPDATE folder_rules
        SET name=?, conditions=?, condition_logic=?, actions=?,
            priority=?, enabled=?, stop_processing=?
        WHERE id=?
    """, (name, json.dumps(conditions), condition_logic, json.dumps(actions),
          priority, int(enabled), int(stop_processing), rule_id))
    conn.commit()
    conn.close()


def delete_folder_rule(rule_id):
    conn = get_connection()
    conn.execute("DELETE FROM folder_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


def increment_rule_hits(rule_id):
    conn = get_connection()
    conn.execute("UPDATE folder_rules SET hits=hits+1 WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()
