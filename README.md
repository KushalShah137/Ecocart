# EcoCart — Sustainable E-Commerce Platform with Eco Swap Recommendations

A complete, database-driven e-commerce application for a DBMS project review.
Every product carries a transparent **Eco-Score**, and **Eco Swap** recommends a
comparable product in the same category with a better score and a similar price —
computed live by a rule-based PL/SQL function, not hard-coded.

| Layer | Technology |
|---|---|
| Database | Oracle Database XE 21c (schema `ECOCART`, service `XEPDB1`; change `.env` to `FREEPDB1` for Oracle 23ai/26ai Free) |
| Backend | Python 3.11+, Flask 3, python-oracledb (thin mode — no Instant Client needed) |
| Frontend | Jinja2, HTML, CSS, vanilla JavaScript, Chart.js (dashboard) |
| Tests | pytest — 31 route/logic tests (no DB needed) + 10 live Oracle integration tests |

---

## Static product catalogue (no API key required)

The project includes a 104-item curated catalogue using real-world product and brand names across eight categories. Prices and stock are static illustrative values, not live retailer offers. Product images are local category illustrations rather than product photographs. Eco-Scores are illustrative estimates based on assumed inputs, not verified product sustainability claims. See `CATALOG_DATA_SOURCES.md` and `data/real_catalog.csv`.

For an existing Oracle database, after the app dependencies and `.env` are configured, run:

```bat
.venv\Scripts\activate
python scripts/load_real_catalog.py
```

The loader updates existing product rows in place to preserve product IDs and foreign keys, deactivates surplus old catalogue entries, regenerates illustrative Eco-Scores, and writes matching local SVG category illustrations. It does not connect to retailer APIs or change live prices.

## 1. Quick start

```bash
# 0. Prerequisites: Oracle XE 21c running with XEPDB1 open (or Oracle 23ai/26ai Free with FREEPDB1); Python 3.11+
cd ecocart
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Configure the connection (only placeholders are committed)
The supplied local .env is configured with ECOCART_DB_PASSWORD=aman. Ensure the Oracle ECOCART user password is also aman; SYSTEM password is separate.

# 2. Create the ECOCART user ONCE as SYS (skip if it already exists on your installation)
sql sys/<sys-password>@localhost:1521/XEPDB1 as sysdba @db/00_create_user.sql
#    (SQL*Plus, SQLcl or SQL Developer all work; set the same password you put in .env)

# 3. Create / migrate schema, views, PL/SQL and load the demo dataset — one command
python scripts/init_db.py

# 4. Run
python app.py
# -> http://127.0.0.1:5000   sign in with demo@example.com / Demo@1234
```

`scripts/init_db.py` runs the files in `db/` in order through python-oracledb, so you
do not need SQL*Plus. It is safe to re-run: the runner skips already-existing tables/indexes/columns,
the migration only adds missing columns, and every seed `INSERT` carries
`IGNORE_ROW_ON_DUPKEY_INDEX`, so duplicates are skipped.

Prefer SQL Developer? Run the same files by hand, in this order, as `ECOCART`:
`01_schema.sql → 02_indexes.sql → 03_views.sql → 04_plsql.sql → 06_migrations.sql → 05_seed_data.sql`.

---

## 2. Demo accounts (synthetic, example.com)

| Account | Password | Purpose |
|---|---|---|
| `demo@example.com` | `Demo@1234` | Customer with history, an active cart, reviews |
| `priya.demo@example.com` | `Priya@1234` | Second customer (useful to prove authorization isolation) |
| `admin@example.com` | `Admin@1234` | Role `ADMIN` (same storefront; role column available for extension) |

Passwords are stored as **scrypt** hashes (Werkzeug). The other 37 synthetic customers
have unique, undocumented passwords. No real person's data is used anywhere.

---

## 3. Project layout

```
ecocart/
├── app.py                      Flask entry point
├── config.py                   Settings from environment (.env via python-dotenv)
├── requirements.txt  .env.example  pytest.ini  .gitignore
├── ecocart/                    Application package
│   ├── __init__.py             create_app(): blueprints, filters, error pages, /health
│   ├── db.py                   Connection pool, query helpers, transaction(), error mapping
│   ├── security.py             scrypt hashing, CSRF protection, login_required
│   ├── eco_methodology.py      Eco-Score formula (mirrors FN_COMPUTE_ECO_SCORE)
│   ├── services/               catalog, ecoswap, cart, orders, reviews, users, analytics
│   ├── blueprints/             main, shop, auth, cart (+checkout), orders, reviews, dashboard
│   ├── templates/              Jinja2 pages (base, index, shop, product, cart, checkout, orders/, auth/, errors/)
│   └── static/                 css/style.css, js/app.js, img/products/*.svg
├── db/
│   ├── 00_create_user.sql      run once as SYS
│   ├── 01_schema.sql           the ten tables, PK/FK/UNIQUE/CHECK/NOT NULL
│   ├── 02_indexes.sql          secondary indexes
│   ├── 03_views.sql            7 views (catalogue, order summary, analytics, missing data)
│   ├── 04_plsql.sql            functions, ECOCART_PKG (place_order, cancel_order, eco_swap), 1 trigger
│   ├── 05_seed_data.sql        GENERATED synthetic dataset (idempotent)
│   ├── 06_migrations.sql       safe column/constraint migration for pre-existing tables
│   ├── 99_reset_data.sql       optional: empty all tables without dropping
│   └── demo_queries.sql        16 numbered demonstration sections for the review
├── scripts/
│   ├── init_db.py              runs the db/ scripts via python-oracledb
│   ├── inspect_schema.py       reports existing tables / missing columns / invalid objects
│   ├── seed_data.py            deterministic generator: --sql | --load | --validate
│   ├── catalog_data.py         static real-world product names/brands and demo price values
│   ├── generate_images.py      local SVG illustrations per product
│   ├── import_dataset.py       original-dataset importer (idempotent, reports rejects)
│   └── run_tests.sh
├── data/original/              drop the original CSVs here (see README inside)
└── tests/
    ├── test_logic.py           methodology, dataset consistency, security, SQL splitter
    ├── test_routes.py          every page/form/API with an in-memory fake of the service layer
    └── test_oracle_integration.py  live PL/SQL checkout, rollback, Eco Swap (auto-skips without Oracle)
```

---

## 4. Database design

Ten tables, all preserved with the names from the brief:

```
CATEGORY 1──∞ PRODUCT 1──1 PRODUCT_SUSTAINABILITY
APP_USER 1──∞ CART 1──∞ CART_ITEM ∞──1 PRODUCT
APP_USER 1──∞ CUSTOMER_ORDER 1──∞ ORDER_ITEM ∞──1 PRODUCT
CUSTOMER_ORDER 1──1 PAYMENT
APP_USER 1──∞ REVIEW ∞──1 PRODUCT
```

Highlights (`db/01_schema.sql`):

* IDENTITY primary keys; FKs on every relationship; `ON DELETE CASCADE` only where a child
  cannot exist without its parent (items, payment, sustainability, reviews).
* UNIQUE: `APP_USER.EMAIL`, `CUSTOMER_ORDER.ORDER_REF`, one sustainability row per product,
  one line per product per cart/order, **one payment per order** (prevents duplicate
  payments), **one review per customer per product** (review policy).
* CHECK: price > 0, stock ≥ 0, quantity 1–50, rating 1–5, Eco-Score 0–100,
  `total_amount = subtotal + shipping_fee`, `line_total = quantity * unit_price`,
  status enumerations, carbon value and unit present together or absent together.
* `DATA_ORIGIN` (`ORIGINAL` / `SYNTHETIC` / `LIVE`) on users, products, sustainability,
  orders and reviews keeps imported, generated and real website rows distinguishable.
* `ORDER_ITEM.UNIT_PRICE` captures the purchase-time price; later price changes never alter history.

**Views** (`03_views.sql`): `V_PRODUCT_CATALOG` (single source for product cards),
`V_ORDER_SUMMARY`, `V_CATEGORY_SUSTAINABILITY`, `V_ECO_SCORE_DISTRIBUTION`,
`V_MONTHLY_SALES`, `V_POPULAR_PRODUCTS`, `V_MISSING_SUSTAINABILITY`.

**PL/SQL** (`04_plsql.sql`):

| Object | Purpose |
|---|---|
| `FN_COMPUTE_ECO_SCORE` | the scoring formula (deterministic) |
| `FN_ECO_GRADE`, `FN_PRODUCT_AVG_RATING`, `FN_CART_TOTAL`, `FN_SHIPPING_FEE` | helpers used by SQL and reports |
| `ECOCART_PKG.PLACE_ORDER` | checkout: locks cart + products (`FOR UPDATE`, deterministic order), validates stock/active/quantity, recomputes totals from DB prices, inserts order + items, reduces stock, inserts exactly one payment, closes the cart; raises `ORA-2001x/20030` on any problem |
| `ECOCART_PKG.CANCEL_ORDER` | ownership check, restores stock, refunds/fails the payment |
| `ECOCART_PKG.ECO_SWAP` | the recommendation engine, returns a `SYS_REFCURSOR` |
| `ECOCART_PKG.ADJUST_STOCK` | concurrency-safe stock delta |
| `TRG_CART_ITEM_TOUCH` | the only trigger — stamps `CART.UPDATED_AT` on item insert/update |

The package never commits. Flask wraps each call in `transaction()` — commit on success,
rollback on any exception — so an order, its items, the stock change and the payment are
all-or-nothing. A declined demo payment (`simulate_failure = 1`, available under
"Testing tools" on the checkout page) proves it: no order, no stock change, no payment row.

---

## 5. Eco-Score methodology (and its honest provenance)

```
eco_score = 0.40 × material_score + 0.25 × packaging_score
          + 0.20 × recyclability_pct + 0.15 × durability_score        (each 0–100)
```

Grades: A ≥ 80, B ≥ 65, C ≥ 50, D ≥ 35, E < 35. Material and packaging classes are
listed in `scripts/catalog_data.py`; every `PRODUCT_SUSTAINABILITY.SCORE_SOURCE` records
the exact inputs used.

The demo inputs are plausible **assumptions**, labelled `DATA_ORIGIN = 'SYNTHETIC'` and
described in the UI as *demo estimates*. They are not measured, audited or certified
environmental performance. Carbon footprint values are shown only for the 21 products
that carry a labelled demo estimate (`kg CO2e per unit (demo estimate)`); every other
product shows "not available" instead of a guess. Eight products deliberately have **no**
sustainability record so the incomplete-data path (no badge, no Eco Swap, listed on the
Sustainability page) can be demonstrated.

---

## 6. Eco Swap

Rules, enforced inside Oracle (`ECOCART_PKG.ECO_SWAP`, also shown as plain SQL in
`demo_queries.sql` §13):

1. same category as the original;
2. a sustainability record with a strictly higher Eco-Score;
3. price within ± tolerance (default 20 %, `ECO_SWAP_PRICE_TOLERANCE` in `.env`;
   adjustable per product page with a slider that calls `/api/eco-swap/<id>?tolerance=`);
4. active and in stock.

Ordered by Eco-Score desc, then closeness in price. Each card shows the score gain, the
rupee difference, why it qualifies, material/packaging and stock. When nothing qualifies the
page shows an informative empty state (try *Plastic Straws (100-pack)* at ₹99).
It is a deterministic rule set — the UI says "not AI" explicitly.

72 of the 115 scored products have at least one qualifying swap immediately after seeding,
including the brief's example: *Polyester Laptop Backpack 25L* (Eco 32) → *Recycled-Fabric
Laptop Backpack 25L* (Eco 78).

---

## 7. The demo dataset

`scripts/seed_data.py` is a deterministic generator (fixed seed) producing:

| Table | Rows | Notes |
|---|---|---|
| CATEGORY | 8 | Electronics, Clothing, Home & Kitchen, Personal Care, Bags, Stationery, Reusables, Lifestyle |
| PRODUCT | 123 | fictional Indian brands, INR prices, stock, conventional/eco pairs |
| PRODUCT_SUSTAINABILITY | 115 | 8 products intentionally unscored |
| APP_USER | 40 | 3 documented demo accounts + 37 fictional customers (example.com) |
| CUSTOMER_ORDER | 90 | last 12 months; DELIVERED/SHIPPED/CONFIRMED/PLACED/CANCELLED |
| ORDER_ITEM | 170 | purchase-time prices (15 % at a historical promo price) |
| PAYMENT | 90 | one per order; status consistent with order status and method |
| REVIEW | 72 | only from customers whose order of that product was delivered (verified) |
| CART / CART_ITEM | 7 / 17 | active carts for the demo accounts and four others |

`--validate` checks every invariant (FKs, totals = Σ items, shipping rule, payment amounts,
status consistency, unique review pairs, Eco Swap coverage) and is run in the test-suite.
Regenerate with `python scripts/seed_data.py --sql` (rewrites `db/05_seed_data.sql`) or load
directly with `--load`.

### Original dataset (Indian E-Commerce Sales & Customer Analytics)

It was **not available** when this project was built (the earlier attempt had already failed
on a missing `customers.csv`), so nothing from it is in the seed. To add it later:

```bash
python scripts/import_dataset.py --dir data/original --dry-run   # validate + counts only
python scripts/import_dataset.py --dir data/original             # import
```

The importer maps columns by name (override with `--mapping file.json`), stores source keys
so re-runs skip existing rows, **rejects** orders whose customer/product is missing instead
of inventing them, pseudonymises customer e-mails (`orig-<id>@example.com`, unusable
passwords), and prints imported/rejected counts per table. Imported rows are
`DATA_ORIGIN = 'ORIGINAL'` and remain distinguishable in every view and on the dashboard.

---

## 8. Website features

* **Home** — branding, nav (Home | Shop | Categories | Eco Swap | Sustainability | My Orders | Cart | Account),
  search, live statistics, category browsing, featured and highest-scoring products, Eco Swap showcase.
* **Shop** — cards with image, INR price, category, rating + review count, Eco-Score badge;
  search, category / price / Eco-Score / stock filters, 8 sort orders, pagination — all pushed to Oracle
  (`OFFSET … FETCH`, bind variables, whitelisted sort keys).
* **Product** — full details, availability, sustainability profile (material, packaging, recyclability,
  carbon only when available, explanation, source), reviews with histogram, review form (one per
  customer, verified-purchase flag), add-to-cart, Eco Swap panel with tolerance slider and empty state.
* **Auth** — register (validation, scrypt), login/logout, secure session cookie (HttpOnly, SameSite=Lax),
  CSRF token on every state-changing request, open-redirect protection, account/profile/password page.
* **Cart** — persisted in `CART`/`CART_ITEM`; add, update, remove (AJAX with no-JS fallback);
  server-side prices and totals; stock and quantity validation; free delivery over ₹999.
* **Checkout** — Cash on Delivery + three clearly-labelled demo methods; runs `ECOCART_PKG.PLACE_ORDER`
  in one transaction; confirmation page; failure simulation.
* **Orders** — list and detail with purchase-time prices, payment status, cancellation with stock restore.
  Other customers' orders return 404 — rows are only ever selected `WHERE user_id = :me`.
* **Dashboard** — tiles and six Chart.js charts fed by `/api/dashboard` (Eco-Score bands, category
  averages, monthly sales, revenue by category, popular products from order records, order status) plus
  tables for most sustainable, category sustainability, popular and top-rated. Nothing is hard-coded.
* **Sustainability** — methodology, grade table, provenance notice and the missing-data report.
* Responsive layout, loading/empty/error states, friendly 400/403/404/500 pages, `/health` endpoint.

Security: parameterised SQL everywhere, no string-built filters or sort clauses, scrypt hashing,
session hardening, CSRF, server-side validation, safe error mapping (`ORA-20xxx` messages surface,
everything else is generic), credentials only via environment.

---

## 9. Running the SQL demonstration

Open `db/demo_queries.sql` in SQL Developer connected as `ECOCART` and run it section by section:
constraints inventory, joins, GROUP BY/HAVING, CASE bands, nested and correlated subqueries,
EXISTS/NOT EXISTS, purchase history, monthly/day-of-week analysis, analytic functions (RANK, LAG,
running totals), rating summaries, sustainability comparisons, Eco Swap in SQL and via the package,
a transactional checkout + declined-payment demo that rolls itself back, the views, and four
constraint violations that are expected to fail.

---

## 10. Tests

```bash
pytest                       # all; Oracle tests auto-skip if the DB is unreachable
pytest tests/test_oracle_integration.py -v   # live PL/SQL tests (needs .env + seeded DB)
```

What is covered: Eco-Score formula and grades; generated dataset meets every target and invariant;
password hashing/validation; sort whitelist and bind-only filters; SQL script splitting; importer
helpers; every public and protected page; search/filter/sort/pagination; product page with and
without sustainability data; Eco Swap API and tolerance; CSRF enforcement; login/logout/registration
validation; cart add/update/remove with totals and stock checks; checkout success (stock reduced,
cart cleared, confirmation); declined payment leaves nothing behind; invalid method/address;
order history and cross-customer isolation; cancellation restores stock; review policy; profile
update; open-redirect block; dashboard API shape. The Oracle integration file adds: connection and
object validity, seed counts, seed idempotency, totals = items, `PLACE_ORDER` stock/payment,
`ORA-20030` rollback, overselling (`ORA-20011`), cancel ownership (`ORA-20040`), Eco Swap rules, views
and constraint rejections.

### Verification status at hand-over (please read)

The project was built in an environment **without an Oracle instance**, and the author's machine was
not reachable from it. Therefore:

* ✅ Executed and passing here: the 31 route/logic tests (`tests/test_logic.py`, `tests/test_routes.py`),
  dataset validation, SQL script parsing, image generation, page rendering.
* ⚠️ **Not yet executed against a live database**: `scripts/init_db.py`, the PL/SQL compilation,
  `db/05_seed_data.sql`, `demo_queries.sql` and `tests/test_oracle_integration.py`. They were written
  carefully for Oracle 23ai/26ai syntax, but the first run on your machine is the real test. If anything
  fails, `init_db.py` prints the exact statement and any `USER_ERRORS` compile messages; run
  `python scripts/inspect_schema.py` to see the state of the schema.

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| `DPY-6005 / ORA-12541` | Oracle listener not running or wrong `ECOCART_DB_DSN`; check `lsnrctl status` and that the service in `.env` is open (`XEPDB1` for XE 21c; `FREEPDB1` for Oracle Free) |
| `ORA-01017 invalid username/password` | `.env` password must match the one used in `00_create_user.sql` |
| `/health` returns `degraded` | same connection problem; the page explains which setting to check |
| "missing columns" from `inspect_schema.py` | run `python scripts/init_db.py --only 06_migrations.sql` |
| Identity collision after manual inserts | the seed script's final `ALTER TABLE … START WITH LIMIT VALUE` resets the sequences; re-run `05_seed_data.sql` |
| Want a clean dataset | `db/99_reset_data.sql` then `python scripts/init_db.py --only 05_seed_data.sql` |


### EcoSwap matching update (existing Oracle database)

EcoSwap now requires a recognized product-function match in addition to a higher estimated Eco-Score, the configured price window, and in-stock status. The Oracle helper `FN_PRODUCT_SWAP_GROUP` deliberately returns `NULL` for product types it cannot classify, so those items are not auto-matched. This prevents category-level false positives such as adhesive tape being recommended as a substitute for a notebook, or a live plant being recommended in place of cocopeat growing medium.

To update an existing database without reseeding or resetting data, activate the project virtual environment and run from the project root:

```bat
python scripts/init_db.py --only 04_plsql.sql
```

This recompiles the PL/SQL functions/package only; it does not reload catalogue rows or reset user/order data. Restart the Flask app afterward. Eco-Scores and prices remain illustrative demo values, not verified product-level environmental assessments or live prices.
