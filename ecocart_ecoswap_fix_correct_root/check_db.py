"""Quick Oracle connection check for EcoCart:  python check_db.py
Prints the exact ORA-/DPY- error instead of the website's generic message."""
import oracledb

from config import Config

print(f"Connecting as {Config.ORACLE_USER} to {Config.ORACLE_DSN} ...")
try:
    with oracledb.connect(user=Config.ORACLE_USER,
                          password=Config.ORACLE_PASSWORD,
                          dsn=Config.ORACLE_DSN) as conn:
        cur = conn.cursor()
        cur.execute("select sys_context('USERENV','CON_NAME'), user from dual")
        pdb, user = cur.fetchone()
        print(f"OK - connected to PDB {pdb} as {user}")
        cur.execute("select count(*) from user_tables")
        n = cur.fetchone()[0]
        print(f"{n} tables in schema" + ("  (empty - run: python scripts/init_db.py)" if n == 0 else ""))
except oracledb.Error as e:
    msg = str(e)
    print("FAILED:", msg)
    if "12514" in msg or "DPY-6001" in msg:
        print("-> Wrong service name. Run `lsnrctl status` and use the PDB name it lists "
              "(FREEPDB1 for 23ai/26ai Free, XEPDB1 for 21c XE) in ECOCART_DB_DSN.")
    elif "12541" in msg or "DPY-6005" in msg:
        print("-> Listener not running / database stopped. Start the Oracle service "
              "(Windows: services.msc -> OracleServiceFREE and OracleOraDB..TNSListener).")
    elif "01017" in msg:
        print("-> Wrong username/password, or the ECOCART user was never created. "
              "Run db/00_create_user.sql as SYS with the same password as in .env.")
    elif "28000" in msg:
        print("-> Account locked. As SYS: ALTER USER ecocart ACCOUNT UNLOCK;")