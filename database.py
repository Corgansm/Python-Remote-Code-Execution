import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="attacker.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT,
                port INTEGER,
                connected_at TEXT,
                disconnected_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id INTEGER,
                timestamp TEXT,
                direction TEXT,
                content TEXT,
                ip TEXT,
                port INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.commit()

    def log_connection(self, ip, port):
        c = self.conn.cursor()
        c.execute("INSERT INTO connections (ip, port, connected_at) VALUES (?, ?, ?)",
                  (ip, port, datetime.now().isoformat()))
        self.conn.commit()
        return c.lastrowid

    def update_disconnect_time(self, connection_db_id):
        c = self.conn.cursor()
        c.execute("UPDATE connections SET disconnected_at=? WHERE id=?",
                  (datetime.now().isoformat(), connection_db_id))
        self.conn.commit()

    def log_message(self, connection_db_id, content, direction):
        # Get IP and port for this connection
        c = self.conn.cursor()
        c.execute("SELECT ip, port FROM connections WHERE id=?", (connection_db_id,))
        row = c.fetchone()
        ip, port = row if row else ("Unknown", 0)
        c.execute("INSERT INTO messages (connection_id, timestamp, direction, content, ip, port) VALUES (?, ?, ?, ?, ?, ?)",
                  (connection_db_id, datetime.now().isoformat(), direction, content, ip, port))
        self.conn.commit()

    def get_all_messages(self):
        c = self.conn.cursor()
        c.execute("SELECT id, connection_id, timestamp, direction, content, ip, port FROM messages ORDER BY timestamp DESC")
        return c.fetchall()

    def search_messages(self, search_term):
        c = self.conn.cursor()
        c.execute("""
            SELECT id, connection_id, timestamp, direction, content, ip, port
            FROM messages
            WHERE content LIKE ?
            ORDER BY timestamp DESC
        """, (f"%{search_term}%",))
        return c.fetchall()

    def delete_message(self, timestamp, connection, direction, content):
        ip, port = connection.split(":")
        c = self.conn.cursor()
        c.execute("""
            DELETE FROM messages
            WHERE timestamp=? AND ip=? AND port=? AND direction=? AND content=?
        """, (timestamp, ip, port, direction, content))
        self.conn.commit()

    def set_setting(self, key, value):
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    def clear_database(self):
        c = self.conn.cursor()
        c.execute("DELETE FROM messages")
        c.execute("DELETE FROM connections")
        c.execute("DELETE FROM settings")
        self.conn.commit()

    def close_all_connections(self):
        self.conn.close()