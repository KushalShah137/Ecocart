"""
Oracle connectivity for EcoCart (python-oracledb, thin mode).

  get_connection()  - standalone connection (scripts)
  get_db()          - per-request pooled connection, released at teardown
  query / query_one - SELECT helpers returning dicts with lower-case keys
  transaction()     - context manager: commit on success, rollback on any error

All SQL in the services uses bind variables (:name). Sort keys and filters are
whitelisted in the services, so no user input is ever concatenated into SQL.
"""
import os
import sys
from contextlib import contextmanager

import oracledb
from flask import current_app, g

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config  # noqa: E402

_pool = None


class DBError(Exception):
    """User-presentable database/business error (message is safe to show)."""


def _params():
    cfg = current_app.config if current_app else Config.__dict__
    return dict(user=cfg["ORACLE_USER"], password=cfg["ORACLE_PASSWORD"], dsn=cfg["ORACLE_DSN"])


def get_connection():
    """Standalone connection using .env settings (used by scripts)."""
    return oracledb.connect(user=Config.ORACLE_USER, password=Config.ORACLE_PASSWORD, dsn=Config.ORACLE_DSN)


def get_pool():
    global _pool
    if _pool is None:
        cfg = current_app.config
        _pool = oracledb.create_pool(min=cfg["ORACLE_POOL_MIN"], max=cfg["ORACLE_POOL_MAX"], increment=1,
                                     **_params())
    return _pool


def get_db():
    if "db" not in g:
        g.db = get_pool().acquire()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.rollback()      # never leak an open transaction back to the pool
        finally:
            get_pool().release(conn)


def init_app(app):
    app.teardown_appcontext(close_db)


def _rows_as_dicts(cur):
    cols = [d[0].lower() for d in cur.description]
    out = []
    for row in cur.fetchall():
        rec = {}
        for c, v in zip(cols, row):
            if isinstance(v, oracledb.LOB):
                v = v.read()
            rec[c] = v
        out.append(rec)
    return out


def query(sql, **binds):
    cur = get_db().cursor()
    cur.execute(sql, binds)
    return _rows_as_dicts(cur)


def query_one(sql, **binds):
    rows = query(sql, **binds)
    return rows[0] if rows else None


def execute(sql, **binds):
    """Executes a DML statement on the request connection (no commit)."""
    cur = get_db().cursor()
    cur.execute(sql, binds)
    return cur.rowcount


@contextmanager
def transaction():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def friendly_error(exc) -> str:
    """Maps Oracle / package errors to a message safe for the user."""
    msg = str(exc)
    if isinstance(exc, oracledb.DatabaseError):
        err = exc.args[0] if exc.args else None
        code = getattr(err, "code", None)
        text = getattr(err, "message", msg)
        if code and 20000 <= code <= 20999:          # RAISE_APPLICATION_ERROR from ECOCART_PKG
            return text.split("ORA-%d:" % code, 1)[-1].split("\n")[0].strip()
        if code == 1:
            return "That record already exists."
        if code in (2290, 2291, 1400, 12899):
            return "The data you submitted is not valid."
        return "A database error occurred. Please try again."
    return msg if isinstance(exc, DBError) else "Something went wrong. Please try again."
