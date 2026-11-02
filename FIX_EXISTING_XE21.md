# Fix EcoCart on Oracle XE 21c (existing partial setup)

This patch targets the Oracle XE 21c installation using service `XEPDB1`. It keeps existing tables/data and repairs the schema/seed initialization.

## 1. Preserve your current `.env`

Do **not** replace `.env` with `.env.example`. Open the existing `.env` next to `app.py` and ensure these values match your working Oracle account:

```env
ECOCART_DB_USER=ecocart
ECOCART_DB_PASSWORD=aman
ECOCART_DB_DSN=localhost:1521/XEPDB1
ECOCART_DB_POOL_MIN=1
ECOCART_DB_POOL_MAX=4
```

This configured package expects the Oracle `ECOCART` user password to be `aman`. If your existing Oracle `ECOCART` account still uses a different password, reset it as `SYSTEM_CHECK` with `ALTER USER ecocart IDENTIFIED BY "aman" ACCOUNT UNLOCK;`. The `SYSTEM` administrator password is separate and is not changed by this setting. The Python project reads `.env` automatically.

## 2. Replace project files

Extract this patched ZIP to a temporary folder. Copy the patched `db` folder, `scripts` folder, `config.py`, `.env.example`, and `README.md` over the same locations in your existing project. Do not overwrite `.env`, and do not delete your existing `ecocart` package, `data`, `tests`, or `static` assets. The ZIP already contains the full project tree, so the simplest option is to back up your existing folder and extract the whole patched project into a new folder, then copy your existing `.env` into it.

## 3. Run repair and initialization from the project root

Open Command Prompt in the folder containing `app.py`, activate your venv, and run:

```bat
.venv\Scripts\activate
python check_db.py
python scripts\init_db.py
```

The patched migration widens `PRODUCT_SUSTAINABILITY.CARBON_FOOTPRINT_UNIT` to `VARCHAR2(80)` before seed loading. The initializer reports existing objects as `already present`, not as failures. It runs schema, indexes, views, PL/SQL, migrations, and seed data in order.

If you prefer a single launcher after placing your existing `.env` in the project root, double-click `run_ecocart.bat`. It checks the connection, initializes the schema/data, and starts Flask only if the previous steps succeed.

Or, after initialization ends with `0 errors`, start the site manually with `python app.py`. Then open http://127.0.0.1:5000. Demo account: `demo@example.com` / `Demo@1234`.

## Important

- Do not run `db/00_create_user.sql` again; your ECOCART user already exists.
- Do not drop tables or run a reset script.
- For Oracle 23ai/26ai Free instead, set the DSN to `localhost:1521/FREEPDB1`.
