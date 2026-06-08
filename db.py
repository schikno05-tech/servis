"""
Слой базы данных: работает и с SQLite (локально), и с PostgreSQL (на хостинге).
Выбор через переменную окружения DATABASE_URL:
  • не задана           -> SQLite (файл servis.db рядом)
  • postgres://... или postgresql://... -> PostgreSQL
"""
import os, sqlite3
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = DATABASE_URL.startswith("postgres")

if IS_PG:
    import psycopg2, psycopg2.extras

BASE = os.path.dirname(__file__)
SQLITE_PATH = os.path.join(BASE, "servis.db")


def _to_pg(sql: str) -> str:
    """Преобразует '?' плейсхолдеры SQLite в '%s' для PostgreSQL."""
    return sql.replace("?", "%s")


class Cur:
    """Обёртка над курсором: единый интерфейс execute/fetch для обеих БД."""
    def __init__(self, raw, is_pg):
        self.raw = raw; self.is_pg = is_pg
    def execute(self, sql, params=()):
        self.raw.execute(_to_pg(sql) if self.is_pg else sql, params)
        return self
    def fetchone(self):
        return self.raw.fetchone()
    def fetchall(self):
        return self.raw.fetchall()
    @property
    def lastrowid(self):
        return self.raw.lastrowid
    def __iter__(self):
        return iter(self.raw.fetchall())


class Conn:
    """Обёртка соединения с .execute(), .commit(), курсором как dict-row."""
    def __init__(self):
        if IS_PG:
            self.c = psycopg2.connect(DATABASE_URL)
        else:
            self.c = sqlite3.connect(SQLITE_PATH)
            self.c.row_factory = sqlite3.Row
            self.c.execute("PRAGMA foreign_keys=ON")
    def cursor(self):
        if IS_PG:
            return Cur(self.c.cursor(cursor_factory=psycopg2.extras.RealDictCursor), True)
        return Cur(self.c.cursor(), False)
    def execute(self, sql, params=()):
        cur = self.cursor(); cur.execute(sql, params); return cur
    def commit(self): self.c.commit()
    def rollback(self): self.c.rollback()
    def close(self): self.c.close()
    def __enter__(self): return self
    def __exit__(self, *a):
        if any(a): self.rollback()
        else: self.commit()


def get_conn():
    return Conn()


# SQL-различия: автоинкремент-первичный ключ
def pk():
    return "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY"

def now_default():
    return "now()" if IS_PG else "CURRENT_TIMESTAMP"
