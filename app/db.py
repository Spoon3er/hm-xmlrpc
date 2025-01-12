import sqlite3
from sqlite3 import Error
import logging


class Database:
    """SQLite database manager."""

    def __init__(self, db_file: str, logger: logging.Logger) -> None:
        self.db_file = db_file
        self.logger = logger
        self.conn = None
        self.cur = None

    def _create_device_table(self) -> None:
        """Create devices table if it doesn't exist."""
        create_table = """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                interface TEXT NOT NULL,
                device_id TEXT DEFAULT '',
                param TEXT DEFAULT '',
                value TEXT DEFAULT '',
                UNIQUE(device_id, param)
            );
        """
        self.execute(create_table)

        create_index = """
            CREATE INDEX IF NOT EXISTS idx_device_param ON devices(device_id, param);
        """
        self.execute(create_index)

    def connect(self) -> None:
        """Create database connection and cursor."""
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.cur = self.conn.cursor()
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise

    def execute(self, query: str, params: tuple = None) -> None:
        """Execute SQL query with parameters."""
        if not self.cur:
            raise RuntimeError("No database cursor. Call connect() first")
        try:
            if params:
                self.cur.execute(query, params)
            else:
                self.cur.execute(query)
            self.conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Failed to execute query: {e}")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cur = None
