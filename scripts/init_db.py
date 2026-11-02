#!/usr/bin/env python3
"""
Runs the EcoCart SQL scripts against Oracle in order using python-oracledb,
so no SQL*Plus / SQLcl installation is required.

    python scripts/init_db.py              # schema, indexes, views, PL/SQL, migrations, seed data
    python scripts/init_db.py --no-seed    # objects only
    python scripts/init_db.py --only 03_views.sql

Statement splitting rules (same as SQL Developer):
  * a PL/SQL block (CREATE ... PROCEDURE/FUNCTION/PACKAGE/TRIGGER, DECLARE, BEGIN)
    is terminated by a line containing only "/"
  * any other statement is terminated by ";" at the end of a line
  * SET / PROMPT / SHOW client directives are skipped
"""
import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ecocart.db import get_connection  # noqa: E402

ORDER = ["01_schema.sql", "02_indexes.sql", "03_views.sql", "04_plsql.sql", "06_migrations.sql", "05_seed_data.sql"]
PLSQL_START = re.compile(r"^\s*(CREATE\s+(OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION|PACKAGE|TRIGGER|TYPE)\b|DECLARE\b|BEGIN\b)", re.I)
CLIENT_DIRECTIVE = re.compile(r"^\s*(SET|PROMPT|SHOW|SPOOL|WHENEVER|EXIT)\b", re.I)


def split_statements(text):
    stmts, buf, in_block = [], [], False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not buf and (not line.strip() or line.strip().startswith("--") or CLIENT_DIRECTIVE.match(line)):
            continue
        if line.strip() == "/":
            if buf:
                stmts.append("\n".join(buf).strip())
            buf, in_block = [], False
            continue
        if not buf and PLSQL_START.match(line):
            in_block = True
        buf.append(line)
        if not in_block and line.endswith(";"):
            stmt = "\n".join(buf).strip()[:-1].strip()
            if stmt:
                stmts.append(stmt)
            buf = []
    if buf and "".join(buf).strip():
        stmts.append("\n".join(buf).strip().rstrip(";"))
    return stmts


def run_file(conn, path):
    with open(path, encoding="utf-8") as f:
        stmts = split_statements(f.read())
    cur = conn.cursor()
    ok = skipped = err = 0
    t0 = time.time()
    for s in stmts:
        try:
            cur.execute(s)
            ok += 1
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0]
            if any(code in msg for code in ("ORA-00955", "ORA-01430", "ORA-02275", "ORA-00001", "ORA-02261", "ORA-02264")):
                skipped += 1  # object/column/constraint already exists - idempotent re-run
                continue
            err += 1
            print(f"    ERROR in statement {ok + skipped + err}: {msg}\n      {s[:160].replace(chr(10), ' ')}")
    conn.commit()
    # compilation errors for PL/SQL objects
    cur.execute("SELECT name, type, line, text FROM user_errors WHERE attribute = 'ERROR' ORDER BY name, sequence")
    for name, typ, line, text in cur.fetchall():
        print(f"    COMPILE ERROR {typ} {name} line {line}: {text.strip()}")
    print(f"  {os.path.basename(path)}: {ok} statements ok, {skipped} already present, {err} errors ({time.time() - t0:.1f}s)")
    return err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--only", help="run a single file from db/")
    args = ap.parse_args()
    files = [args.only] if args.only else [f for f in ORDER if not (args.no_seed and f == "05_seed_data.sql")]
    conn = get_connection()
    print("Connected to Oracle", conn.version, "as", conn.username)
    total_err = 0
    for f in files:
        total_err += run_file(conn, os.path.join(ROOT, "db", f))
    conn.close()
    print("Done." if total_err == 0 else f"Finished with {total_err} statement error(s) - review the output above.")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
