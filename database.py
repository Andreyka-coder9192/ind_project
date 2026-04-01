import sqlite3
from datetime import datetime
from typing import Optional, Sequence

DEFAULT_DATE_FORMAT = "dd.mm.yyyy"
DEFAULT_REMINDER_MODE = "both"
VALID_DATE_FORMATS = {
    "dd.mm.yyyy",
    "dd/mm/yyyy",
    "yyyy-mm-dd",
}
VALID_REMINDER_MODES = {
    "off",
    "due_today",
    "day_before",
    "both",
}


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'normal',
                    deadline TEXT NOT NULL,
                    is_done INTEGER NOT NULL DEFAULT 0,
                    last_reminded_on TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    date_format TEXT NOT NULL DEFAULT 'dd.mm.yyyy',
                    reminder_mode TEXT NOT NULL DEFAULT 'both'
                )
                """
            )
            existing_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
            }
            if "priority" not in existing_columns:
                connection.execute(
                    """
                    ALTER TABLE tasks
                    ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'
                    """
                )
            connection.execute(
                """
                UPDATE tasks
                SET priority = 'normal'
                WHERE priority IS NULL OR priority = ''
                """
            )
            settings_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(user_settings)")
            }
            if "reminder_mode" not in settings_columns:
                connection.execute(
                    """
                    ALTER TABLE user_settings
                    ADD COLUMN reminder_mode TEXT NOT NULL DEFAULT 'both'
                    """
                )
            connection.execute(
                """
                UPDATE user_settings
                SET reminder_mode = ?
                WHERE reminder_mode IS NULL OR reminder_mode = ''
                """,
                (DEFAULT_REMINDER_MODE,),
            )
            connection.commit()

    def get_user_date_format(self, user_id: int) -> str:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT date_format
                FROM user_settings
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row is not None and row["date_format"] in VALID_DATE_FORMATS:
                return str(row["date_format"])

            connection.execute(
                """
                INSERT INTO user_settings (user_id, date_format, reminder_mode)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id, DEFAULT_DATE_FORMAT, DEFAULT_REMINDER_MODE),
            )
            cursor = connection.execute(
                """
                SELECT date_format
                FROM user_settings
                WHERE user_id = ?
                """,
                (user_id,),
            )
            ensured_row = cursor.fetchone()
            if ensured_row is not None and ensured_row["date_format"] in VALID_DATE_FORMATS:
                connection.commit()
                return str(ensured_row["date_format"])

            connection.execute(
                """
                UPDATE user_settings
                SET date_format = ?
                WHERE user_id = ?
                """,
                (DEFAULT_DATE_FORMAT, user_id),
            )
            connection.commit()
            return DEFAULT_DATE_FORMAT

    def set_user_date_format(self, user_id: int, date_format: str) -> None:
        if date_format not in VALID_DATE_FORMATS:
            raise ValueError("Некорректный формат даты.")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_settings (user_id, date_format)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET date_format = excluded.date_format
                """,
                (user_id, date_format),
            )
            connection.commit()

    def get_user_reminder_mode(self, user_id: int) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_settings (user_id, date_format, reminder_mode)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id, DEFAULT_DATE_FORMAT, DEFAULT_REMINDER_MODE),
            )
            cursor = connection.execute(
                """
                SELECT reminder_mode
                FROM user_settings
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row is not None and row["reminder_mode"] in VALID_REMINDER_MODES:
                connection.commit()
                return str(row["reminder_mode"])

            connection.execute(
                """
                UPDATE user_settings
                SET reminder_mode = ?
                WHERE user_id = ?
                """,
                (DEFAULT_REMINDER_MODE, user_id),
            )
            connection.commit()
            return DEFAULT_REMINDER_MODE

    def set_user_reminder_mode(self, user_id: int, reminder_mode: str) -> None:
        if reminder_mode not in VALID_REMINDER_MODES:
            raise ValueError("Некорректный режим напоминаний.")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_settings (user_id, reminder_mode)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET reminder_mode = excluded.reminder_mode
                """,
                (user_id, reminder_mode),
            )
            connection.commit()

    def add_task(self, user_id: int, title: str, priority: str, deadline: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (user_id, title, priority, deadline, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    title,
                    priority,
                    deadline,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_tasks(self, user_id: int) -> Sequence[sqlite3.Row]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT id, title, priority, deadline, is_done
                FROM tasks
                WHERE user_id = ?
                ORDER BY
                    is_done ASC,
                    CASE priority
                        WHEN 'important' THEN 0
                        WHEN 'normal' THEN 1
                        WHEN 'low' THEN 2
                        ELSE 1
                    END ASC,
                    deadline ASC,
                    id ASC
                """,
                (user_id,),
            )
            return cursor.fetchall()

    def get_task(self, user_id: int, task_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT id, title, priority, deadline, is_done
                FROM tasks
                WHERE user_id = ? AND id = ?
                """,
                (user_id, task_id),
            )
            return cursor.fetchone()

    def mark_task_done(self, user_id: int, task_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks
                SET is_done = 1
                WHERE id = ? AND user_id = ? AND is_done = 0
                """,
                (task_id, user_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def delete_task(self, user_id: int, task_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM tasks
                WHERE id = ? AND user_id = ?
                """,
                (task_id, user_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def get_tasks_for_reminders(
        self, today_iso: str, tomorrow_iso: str
    ) -> Sequence[sqlite3.Row]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT id, user_id, title, deadline
                FROM tasks
                WHERE is_done = 0
                  AND deadline IN (?, ?)
                  AND (last_reminded_on IS NULL OR last_reminded_on <> ?)
                ORDER BY deadline ASC, id ASC
                """,
                (today_iso, tomorrow_iso, today_iso),
            )
            return cursor.fetchall()

    def mark_task_reminded(self, task_id: int, reminded_on: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET last_reminded_on = ?
                WHERE id = ?
                """,
                (reminded_on, task_id),
            )
            connection.commit()
