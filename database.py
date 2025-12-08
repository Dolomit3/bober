import sqlite3
import logging
from datetime import datetime
from typing import List, Set, Tuple, Optional


class MainDb:
    def __init__(self, db_name: str = "bot.db"):
        self.db_name = db_name
        self.create_tables()

    def create_tables(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            # Таблица чатов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    has_autoposting INTEGER DEFAULT 1,
                    has_autopining INTEGER DEFAULT 1,
                    has_stopwords INTEGER DEFAULT 1,
                    captcha_timeout INTEGER DEFAULT 300,
                    message_cooldown INTEGER DEFAULT 0
                )
            ''')
            # Таблица стоп-слов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stop_words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT UNIQUE
                )
            ''')
            # Таблица статуса капчи
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS captcha_status (
                    user_id INTEGER,
                    chat_id INTEGER,
                    passed INTEGER DEFAULT 0,
                    attempts INTEGER DEFAULT 0,
                    message_id INTEGER,
                    PRIMARY KEY (user_id, chat_id)
                )
            ''')
            # Таблица времени последнего сообщения (для кулдауна)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_messages (
                    user_id INTEGER,
                    chat_id INTEGER,
                    last_message_time TEXT,
                    PRIMARY KEY (user_id, chat_id)
                )
            ''')
            # Таблица закреплённых сообщений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pinned_messages (
                    message_id INTEGER,
                    chat_id INTEGER,
                    PRIMARY KEY (message_id, chat_id)
                )
            ''')
            # Безопасное добавление новых колонок (на случай старой базы)
            try:
                cursor.execute("ALTER TABLE chats ADD COLUMN captcha_timeout INTEGER DEFAULT 300")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE chats ADD COLUMN message_cooldown INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.commit()
        logging.info("Tables created successfully.")

    def add_chat(self, chat_id: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO chats
                (chat_id, has_autoposting, has_autopining, has_stopwords, captcha_timeout, message_cooldown)
                VALUES (?, 1, 1, 1, 300, 0)
            ''', (chat_id,))
            conn.commit()
        logging.info(f"Chat {chat_id} added with all features enabled: autoposting=1, autopining=1, stopwords=1, message_cooldown=0")

    def update_chat_settings(self, chat_id: int, **kwargs):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            for key, value in kwargs.items():
                cursor.execute(f"UPDATE chats SET {key} = ? WHERE chat_id = ?", (value, chat_id))
            conn.commit()
        logging.info(f"Chat {chat_id} settings updated in database")

    def get_all_chats(self) -> List[Tuple]:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id, has_autoposting, has_autopining, has_stopwords, captcha_timeout, message_cooldown FROM chats")
            return cursor.fetchall()

    def delete_chat(self, chat_id: int) -> bool:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
        return deleted

    # === Стоп-слова ===
    def update_stop_words(self, words: List[str]):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stop_words")
            cursor.executemany("INSERT OR IGNORE INTO stop_words (word) VALUES (?)", [(w,) for w in words])
            conn.commit()

    def get_all_stop_words(self) -> Set[str]:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT word FROM stop_words")
            return {row[0].lower() for row in cursor.fetchall()}

    def have_stop_words(self, chat_id: int) -> bool:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT has_stopwords FROM chats WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            return bool(row[0]) if row else False

    # === Кулдаун сообщений ===
    def set_message_cooldown(self, chat_id: int, seconds: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE chats SET message_cooldown = ? WHERE chat_id = ?", (seconds, chat_id))
            conn.commit()
        logging.info(f"Message cooldown set to {seconds} seconds for chat {chat_id}")

    def get_message_cooldown(self, chat_id: int) -> int:
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT message_cooldown FROM chats WHERE chat_id = ?", (chat_id,))
                row = cursor.fetchone()
                if row:
                    return int(row[0])
                else:
                    logging.warning(f"Chat {chat_id} not found when getting message_cooldown, returning 0")
                    return 0
        except Exception as e:
            logging.error(f"Error getting message_cooldown for chat {chat_id}: {e}")
            return 0

    def get_last_message_time(self, user_id: int, chat_id: int) -> Optional[datetime]:
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT last_message_time FROM user_messages WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
                row = cursor.fetchone()
                if row and row[0]:
                    return datetime.fromisoformat(row[0])
                return None
        except Exception as e:
            logging.error(f"Error getting last_message_time: {e}")
            return None

    def update_last_message_time(self, user_id: int, chat_id: int):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_messages (user_id, chat_id, last_message_time)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET last_message_time = excluded.last_message_time
            ''', (user_id, chat_id, now))
            conn.commit()
        logging.info(f"Updated last message time for user {user_id} in chat {chat_id}")

    # === Капча ===
    def check_captcha_status(self, user_id: int, chat_id: int) -> bool:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT passed FROM captcha_status WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            row = cursor.fetchone()
            return row is not None and row[0] == 1

    def update_captcha_status(self, user_id: int, chat_id: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO captcha_status (user_id, chat_id, passed, attempts)
                VALUES (?, ?, 1, 0)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET passed = 1, attempts = 0
            ''', (user_id, chat_id))
            conn.commit()
        logging.info(f"Captcha status updated for user {user_id} in chat {chat_id}")

    def delete_captcha_status(self, user_id: int, chat_id: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM captcha_status WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            conn.commit()
        logging.info(f"Captcha status deleted for user {user_id} in chat {chat_id}")

    def increment_captcha_attempts(self, user_id: int, chat_id: int) -> int:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO captcha_status (user_id, chat_id, attempts, passed)
                VALUES (?, ?, 1, 0)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET
                attempts = attempts + 1,
                passed = 0
            ''', (user_id, chat_id))
            cursor.execute("SELECT attempts FROM captcha_status WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            attempts = cursor.fetchone()[0]
            conn.commit()
            logging.info(f"Captcha attempts for user {user_id} in chat {chat_id}: {attempts}")
            return attempts

    def reset_captcha_attempts(self, user_id: int, chat_id: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE captcha_status SET attempts = 0 WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            conn.commit()

    def get_captcha_attempts(self, user_id: int, chat_id: int) -> int:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT attempts FROM captcha_status WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_captcha_timeout(self, chat_id: int) -> int:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT captcha_timeout FROM chats WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            return row[0] if row else 300

    def set_captcha_timeout(self, chat_id: int, seconds: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE chats SET captcha_timeout = ? WHERE chat_id = ?", (seconds, chat_id))
            conn.commit()

    def update_captcha_message_id(self, user_id: int, chat_id: int, message_id: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO captcha_status (user_id, chat_id, message_id, passed)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET
                message_id = excluded.message_id,
                passed = 0
            ''', (user_id, chat_id, message_id))
            conn.commit()
        logging.info(f"Captcha message_id {message_id} updated for user {user_id} in chat {chat_id}")

    def get_captcha_message_id(self, user_id: int, chat_id: int) -> Optional[int]:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT message_id FROM captcha_status WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            row = cursor.fetchone()
            return row[0] if row else None

    # === Закреплённые сообщения ===
    def insert_pinned_messages(self, messages: list):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.executemany("INSERT OR IGNORE INTO pinned_messages (message_id, chat_id) VALUES (?, ?)",
                               [(m.message_id, m.chat.id) for m in messages])
            conn.commit()
        logging.info(f"Pinned messages inserted: {[m.message_id for m in messages]}")

    def add_pinned_message(self, chat_id: int, message_id: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO pinned_messages (message_id, chat_id) VALUES (?, ?)",
                (message_id, chat_id)
            )
            conn.commit()
        logging.info(f"Добавлено закреплённое сообщение {message_id} в чат {chat_id}")

    def delete_pinned_message(self, chat_id: int, message_id: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pinned_messages WHERE message_id = ? AND chat_id = ?",
                (message_id, chat_id)
            )
            conn.commit()

    def get_pinned_messages(self) -> List[Tuple[int, int]]:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT message_id, chat_id FROM pinned_messages")
            return cursor.fetchall()

    # === Очистка просроченной капчи ===
    def cleanup_expired_captchas(self):
        logging.info("Expired captcha statuses checked and cleaned up.")