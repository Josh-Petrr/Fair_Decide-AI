"""Database access: one shared connection pool, rows returned as dicts."""
import atexit
from contextlib import contextmanager

import pandas as pd
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import DATABASE_URL

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=8, kwargs={"row_factory": dict_row}, open=True)
        atexit.register(close)
    return _pool


def close():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def conn():
    """Connection inside a transaction: commits on success, rolls back on error."""
    with pool().connection() as c:
        yield c


def fetch_all(sql, params=None):
    with conn() as c:
        return c.execute(sql, params).fetchall()


def fetch_one(sql, params=None):
    with conn() as c:
        return c.execute(sql, params).fetchone()


def frame(sql, params=None) -> pd.DataFrame:
    return pd.DataFrame(fetch_all(sql, params))


def as_of():
    return fetch_one("SELECT fd_as_of() AS d")["d"]
