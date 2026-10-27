import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def new_id():
    return uuid.uuid4().hex


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Store:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "agent.sqlite"
        self.directory = directory
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users(
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL, is_admin INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(
                    token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    csrf TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts(
                    key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS threads(
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    title TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(
                    id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id),
                    role TEXT NOT NULL, content TEXT NOT NULL, file_ids TEXT NOT NULL,
                    skills TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id),
                    status TEXT NOT NULL, output TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '', created REAL NOT NULL, finished REAL);
                CREATE UNIQUE INDEX IF NOT EXISTS active_run ON runs(thread_id)
                    WHERE status IN ('queued','running');
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS run_events ON events(run_id,id);
                CREATE TABLE IF NOT EXISTS files(
                    id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id),
                    name TEXT NOT NULL, media_type TEXT NOT NULL, content BLOB NOT NULL,
                    created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS app_config(
                    key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        with sqlite3.connect(self.path, timeout=10) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            yield db

    def query(self, sql, params=()):
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def config(self, key, default=""):
        rows = self.query("SELECT value FROM app_config WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def set_config(self, key, value):
        with self.connect() as db:
            db.execute(
                "INSERT INTO app_config(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def create_user(self, username, password, *, admin=False):
        name = username.strip().lower()
        if not name or not password:
            raise ValueError("账号和密码不能为空")
        uid = new_id()
        with self.connect() as db:
            db.execute(
                "INSERT INTO users VALUES(?,?,?,?)", (uid, name, HASHER.hash(password), int(admin))
            )
        return uid

    def bootstrap_demo(self):
        if not self.query("SELECT 1 FROM users"):
            self.create_user("admin", "123", admin=True)

    def login(self, username, password, peer):
        name = username.strip().lower()
        keys = [digest("user:" + name), digest("peer:" + peer)]
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM attempts WHERE expires<?", (now,))
            db.execute("DELETE FROM sessions WHERE expires<?", (now,))
            for key in keys:
                row = db.execute("SELECT count FROM attempts WHERE key=?", (key,)).fetchone()
                if row and row[0] >= 10:
                    raise PermissionError("登录尝试过多，请稍后重试")
                db.execute(
                    "INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET "
                    "count=count+1",
                    (key, now + 900),
                )
        users = self.query("SELECT * FROM users WHERE username=?", (name,))
        hashed = users[0]["password_hash"] if users else HASHER.hash(secrets.token_hex(16))
        try:
            valid = HASHER.verify(hashed, password) and bool(users)
        except VerificationError:
            valid = False
        if not valid:
            raise ValueError("账号或密码错误")
        token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES(?,?,?,?)",
                (digest(token), users[0]["id"], csrf, now + 43200),
            )
            db.execute("DELETE FROM attempts WHERE key=?", (keys[0],))
        return token, {
            "id": users[0]["id"],
            "username": name,
            "is_admin": bool(users[0]["is_admin"]),
            "csrf_token": csrf,
        }

    def session(self, token):
        rows = self.query(
            "SELECT u.id,u.username,u.is_admin,s.csrf FROM sessions s "
            "JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?",
            (digest(token or ""), time.time()),
        )
        return rows[0] if rows else None

    def own_thread(self, user_id, thread_id):
        rows = self.query("SELECT * FROM threads WHERE id=? AND user_id=?", (thread_id, user_id))
        if not rows:
            raise KeyError("对话不存在")
        return rows[0]

    def add_message(self, thread_id, role, content, files=None, skills=None, *, connection=None):
        args = (
            new_id(),
            thread_id,
            role,
            content,
            json.dumps(files or []),
            json.dumps(skills or []),
            time.time(),
        )
        if connection is not None:
            connection.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?)", args)
        else:
            with self.connect() as db:
                db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?)", args)

    def file(self, thread_id, file_id):
        rows = self.query("SELECT * FROM files WHERE id=? AND thread_id=?", (file_id, thread_id))
        if not rows:
            raise KeyError("附件不存在")
        return rows[0]

    def event(self, run_id, kind, payload):
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(run_id,kind,payload) VALUES(?,?,?)",
                (run_id, kind, json.dumps(payload, ensure_ascii=False)),
            )
