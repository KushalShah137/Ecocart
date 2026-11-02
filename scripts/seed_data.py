#!/usr/bin/env python3
"""
EcoCart seed-data generator and loader.

  python scripts/seed_data.py --sql           # (re)generate db/05_seed_data.sql
  python scripts/seed_data.py --load          # insert directly into Oracle (uses .env)
  python scripts/seed_data.py --validate      # consistency checks on the generated dataset

The generator is deterministic (fixed random seed), so the SQL file and a direct
load always produce the same rows with the same primary keys. Loading is
idempotent: every INSERT carries the IGNORE_ROW_ON_DUPKEY_INDEX hint, so rows
that already exist are skipped and re-running never duplicates anything.

Product names/brands in the catalogue are real-world examples; product prices and
stock are static demo values. Customer accounts, orders and reviews are synthetic.
Eco-Scores are educational estimates from assumed inputs, not certified measurements.
"""
import argparse
import datetime as dt
import os
import random
import sys
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from catalog_data import (B, CATEGORIES, CITIES, FIRST_NAMES, LAST_NAMES, MATERIALS, PACKAGING,  # noqa: E402
                          PRODUCTS, REVIEW_TEMPLATES, STREETS)
from ecocart.eco_methodology import METHODOLOGY_VERSION, compute_eco_score  # noqa: E402

SEED = 20261018
NOW = dt.datetime(2026, 10, 18, 12, 0, 0)        # fixed "generation time" so the dataset is reproducible

# Demo credentials (documented in README). Passwords are hashed with werkzeug scrypt.
DEMO_ACCOUNTS = [
    ("Demo Customer", "demo@example.com", "Demo@1234", "CUSTOMER"),
    ("Priya Demo", "priya.demo@example.com", "Priya@1234", "CUSTOMER"),
    ("EcoCart Admin", "admin@example.com", "Admin@1234", "ADMIN"),
]
SYNTHETIC_USER_PASSWORD_PREFIX = "Seed#"   # synthetic users get unique, undocumented passwords


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def shipping_fee(subtotal: Decimal) -> Decimal:
    return Decimal("0.00") if subtotal >= 999 else Decimal("49.00")


class Dataset:
    def __init__(self):
        self.categories, self.users, self.products, self.sustainability = [], [], [], []
        self.carts, self.cart_items, self.orders, self.order_items, self.payments, self.reviews = [], [], [], [], [], []


def generate(hash_password) -> Dataset:
    rnd = random.Random(SEED)
    d = Dataset()

    # ---- categories ---------------------------------------------------------
    cat_id_by_slug = {}
    for i, (name, slug, desc, icon) in enumerate(CATEGORIES, start=1):
        cat_id_by_slug[slug] = i
        d.categories.append(dict(category_id=i, category_name=name, slug=slug, description=desc, icon=icon))

    # ---- products + sustainability -----------------------------------------
    pid = 0
    for slug, items in PRODUCTS.items():
        for (name, brand, price, mat, pkg, recyc, dur, stock, desc, extra) in items:
            pid += 1
            created = NOW - dt.timedelta(days=rnd.randint(200, 420))
            d.products.append(dict(
                product_id=pid, category_id=cat_id_by_slug[slug], product_name=name, brand=brand,
                description=desc, price=money(price), stock_quantity=stock,
                image_url=f"/static/img/products/p-{pid}.svg", is_active=1,
                is_featured=1 if (extra.get("featured") or name == items[0][0]) else 0, data_origin="ORIGINAL",
                source_key=f"CURATED-{slug}-{pid}", created_at=created))
            if mat is None:
                continue  # deliberately missing sustainability record
            mat_label, mat_score = MATERIALS[mat]
            pkg_label, pkg_score = PACKAGING[pkg]
            score = compute_eco_score(mat_score, pkg_score, recyc, dur)
            expl = _explain(mat_label, pkg_label, recyc, dur, score)
            carbon = extra.get("carbon")
            d.sustainability.append(dict(
                sustainability_id=len(d.sustainability) + 1, product_id=pid, material=mat_label,
                packaging_type=pkg_label, recyclability_pct=Decimal(recyc), eco_score=score,
                carbon_footprint_kg=(Decimal(str(carbon)) if carbon is not None else None),
                carbon_footprint_unit=("kg CO2e per unit (demo estimate)" if carbon is not None else None),
                sustainability_explanation=expl,
                score_source=f"{METHODOLOGY_VERSION}: 0.40 material({mat_score}) + 0.25 packaging({pkg_score}) "
                             f"+ 0.20 recyclability({recyc}) + 0.15 durability({dur}); illustrative estimates, not verified product data",
                data_origin="SYNTHETIC", updated_at=created))

    # ---- users --------------------------------------------------------------
    uid = 0
    for full_name, email, pwd, role in DEMO_ACCOUNTS:
        uid += 1
        city, state, pin = CITIES[uid % len(CITIES)]
        d.users.append(dict(
            user_id=uid, full_name=full_name, email=email, password_hash=hash_password(pwd),
            phone=f"+91 98{rnd.randint(10000000, 99999999)}", address_line=f"{rnd.randint(1, 120)}, {rnd.choice(STREETS)}",
            city=city, state=state, pincode=pin, role=role, is_demo=1, data_origin="SYNTHETIC",
            created_at=NOW - dt.timedelta(days=400)))
    used_emails = {u["email"] for u in d.users}
    while uid < 40:
        fn, ln = rnd.choice(FIRST_NAMES), rnd.choice(LAST_NAMES)
        email = f"{fn.lower()}.{ln.lower()}{rnd.randint(1, 99)}@example.com"
        if email in used_emails:
            continue
        used_emails.add(email)
        uid += 1
        city, state, pin = rnd.choice(CITIES)
        d.users.append(dict(
            user_id=uid, full_name=f"{fn} {ln}", email=email,
            password_hash=hash_password(f"{SYNTHETIC_USER_PASSWORD_PREFIX}{uid}-{rnd.randint(100000, 999999)}"),
            phone=f"+91 9{rnd.randint(100000000, 999999999)}", address_line=f"{rnd.randint(1, 250)}, {rnd.choice(STREETS)}",
            city=city, state=state, pincode=pin, role="CUSTOMER", is_demo=0, data_origin="SYNTHETIC",
            created_at=NOW - dt.timedelta(days=rnd.randint(30, 390))))

    # ---- historical orders ----------------------------------------------------
    prod_by_id = {p["product_id"]: p for p in d.products}
    order_id = 0
    oi_id = 0
    for _ in range(90):
        order_id += 1
        user = rnd.choice(d.users)
        age_days = rnd.randint(0, 365)
        order_date = NOW - dt.timedelta(days=age_days, hours=rnd.randint(0, 23), minutes=rnd.randint(0, 59))
        if order_date < user["created_at"]:
            order_date = user["created_at"] + dt.timedelta(days=rnd.randint(1, 20))
            age_days = (NOW - order_date).days
        n_lines = rnd.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
        chosen = rnd.sample(d.products, n_lines)
        subtotal = Decimal("0.00")
        lines = []
        for p in chosen:
            qty = rnd.choices([1, 2, 3], weights=[65, 25, 10])[0]
            # purchase-time price: occasionally a historical promo price
            unit = p["price"] if rnd.random() > 0.15 else money(p["price"] * Decimal("0.95"))
            line_total = money(unit * qty)
            subtotal += line_total
            lines.append((p["product_id"], qty, unit, line_total))
        ship = shipping_fee(subtotal)
        method = rnd.choices(["COD", "DEMO_UPI", "DEMO_CARD", "DEMO_WALLET"], weights=[30, 40, 20, 10])[0]
        # status by age
        if age_days >= 10:
            status = rnd.choices(["DELIVERED", "CANCELLED"], weights=[92, 8])[0]
        elif age_days >= 4:
            status = rnd.choice(["SHIPPED", "DELIVERED"])
        else:
            status = "CONFIRMED" if method != "COD" else "PLACED"
        if status == "CANCELLED":
            pay_status = "REFUNDED" if method != "COD" else "FAILED"
        elif method == "COD":
            pay_status = "PAID" if status == "DELIVERED" else "PENDING"
        else:
            pay_status = "PAID"
        paid_at = None
        if pay_status in ("PAID", "REFUNDED"):
            paid_at = order_date + (dt.timedelta(minutes=2) if method != "COD" else dt.timedelta(days=rnd.randint(2, 6)))
        ref = f"EC-{order_date:%Y%m%d}-{rnd.randint(0, 999999):06d}"
        d.orders.append(dict(
            order_id=order_id, order_ref=ref, user_id=user["user_id"], order_date=order_date, status=status,
            subtotal=subtotal, shipping_fee=ship, total_amount=subtotal + ship,
            shipping_address=f"{user['address_line']}, {user['city']}, {user['state']} - {user['pincode']}",
            data_origin="SYNTHETIC", source_key=None))
        for (p_id, qty, unit, lt) in lines:
            oi_id += 1
            d.order_items.append(dict(order_item_id=oi_id, order_id=order_id, product_id=p_id, quantity=qty,
                                      unit_price=unit, line_total=lt))
        d.payments.append(dict(
            payment_id=order_id, order_id=order_id, payment_method=method, amount=subtotal + ship,
            status=pay_status, transaction_ref=(f"DEMO-{ref}" if method != "COD" and pay_status != "FAILED" else None),
            paid_at=paid_at, created_at=order_date))

    # ---- reviews: only from customers who actually received the product ---------
    delivered_pairs = {}
    for o in d.orders:
        if o["status"] != "DELIVERED":
            continue
        for oi in d.order_items:
            if oi["order_id"] == o["order_id"]:
                delivered_pairs.setdefault((oi["product_id"], o["user_id"]), o["order_date"])
    pairs = sorted(delivered_pairs.items())
    rnd.shuffle(pairs)
    user_by_id = {u["user_id"]: u for u in d.users}
    sust_by_pid = {s["product_id"]: s for s in d.sustainability}
    rid = 0
    for (p_id, u_id), delivered_on in pairs[:72]:
        rid += 1
        p = prod_by_id[p_id]
        score = sust_by_pid.get(p_id, {}).get("eco_score")
        # mild correlation between eco-score and satisfaction, mostly random
        base = [5, 4, 3, 2, 1]
        weights = [40, 32, 15, 8, 5] if (score or 50) >= 60 else [30, 34, 20, 10, 6]
        rating = rnd.choices(base, weights=weights)[0]
        title, text = rnd.choice(REVIEW_TEMPLATES[rating])
        u = user_by_id[u_id]
        text = text.format(name=p["product_name"], brand=p["brand"], city=u["city"])
        d.reviews.append(dict(review_id=rid, product_id=p_id, user_id=u_id, rating=rating, title=title,
                              review_text=text, is_verified=1, data_origin="SYNTHETIC",
                              created_at=delivered_on + dt.timedelta(days=rnd.randint(3, 25))))

    # ---- active carts for demo + a few others ------------------------------------
    cart_id = 0
    ci_id = 0
    for u in [d.users[0], d.users[1]] + rnd.sample(d.users[3:], 4):
        cart_id += 1
        d.carts.append(dict(cart_id=cart_id, user_id=u["user_id"], status="ACTIVE",
                            created_at=NOW - dt.timedelta(days=1), updated_at=NOW - dt.timedelta(hours=2)))
        for p in rnd.sample(d.products, rnd.randint(1, 3)):
            ci_id += 1
            d.cart_items.append(dict(cart_item_id=ci_id, cart_id=cart_id, product_id=p["product_id"],
                                     quantity=rnd.randint(1, 2), added_at=NOW - dt.timedelta(hours=3)))
    # a checked-out cart for history (belongs to the first synthetic order's customer)
    cart_id += 1
    d.carts.append(dict(cart_id=cart_id, user_id=d.orders[0]["user_id"], status="CHECKED_OUT",
                        created_at=d.orders[0]["order_date"] - dt.timedelta(hours=1), updated_at=d.orders[0]["order_date"]))
    return d


def _explain(mat, pkg, recyc, dur, score):
    bits = [f"Main material: {mat.lower()}.", f"Packaging: {pkg.lower()}.", f"About {recyc}% recyclable at end of life."]
    if dur >= 85:
        bits.append("Designed for years of reuse.")
    elif dur <= 20:
        bits.append("Single-use or short-lived, which lowers the score.")
    bits.append(f"Eco-Score {score}/100 is a demo estimate from the EcoCart v1 formula.")
    return " ".join(bits)


# --------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------
def validate(d: Dataset) -> list[str]:
    errors = []
    cat_ids = {c["category_id"] for c in d.categories}
    user_ids = {u["user_id"] for u in d.users}
    prod_ids = {p["product_id"] for p in d.products}
    order_ids = {o["order_id"] for o in d.orders}
    cart_ids = {c["cart_id"] for c in d.carts}

    if len(d.categories) < 8: errors.append("fewer than 8 categories")
    if not (100 <= len(d.products) <= 150): errors.append(f"product count {len(d.products)} outside 100-150")
    if not (30 <= len(d.users) <= 50): errors.append(f"user count {len(d.users)} outside 30-50")
    if not (60 <= len(d.orders) <= 100): errors.append(f"order count {len(d.orders)} outside 60-100")
    if len(d.order_items) < 100: errors.append("fewer than 100 order items")
    if len(d.reviews) < 50: errors.append(f"fewer than 50 reviews ({len(d.reviews)})")
    if len(d.sustainability) < 0.75 * len(d.products): errors.append("sustainability coverage below 75%")
    if len(d.sustainability) == len(d.products): errors.append("no product left without sustainability data")

    for p in d.products:
        if p["category_id"] not in cat_ids: errors.append(f"product {p['product_id']} bad category")
        if p["price"] <= 0 or p["stock_quantity"] < 0: errors.append(f"product {p['product_id']} bad price/stock")
    for s in d.sustainability:
        if s["product_id"] not in prod_ids: errors.append("sustainability orphan")
        if not 0 <= s["eco_score"] <= 100: errors.append("eco_score out of range")
        if (s["carbon_footprint_kg"] is None) != (s["carbon_footprint_unit"] is None): errors.append("carbon unit mismatch")
    if len({s["product_id"] for s in d.sustainability}) != len(d.sustainability): errors.append("duplicate sustainability")
    if len({u["email"] for u in d.users}) != len(d.users): errors.append("duplicate emails")
    if not all(u["email"].endswith("@example.com") for u in d.users): errors.append("non-example.com email")

    items_by_order = {}
    for oi in d.order_items:
        if oi["order_id"] not in order_ids or oi["product_id"] not in prod_ids: errors.append("order_item orphan")
        if oi["line_total"] != money(oi["quantity"] * oi["unit_price"]): errors.append("line_total mismatch")
        items_by_order.setdefault(oi["order_id"], []).append(oi)
    if len({(oi["order_id"], oi["product_id"]) for oi in d.order_items}) != len(d.order_items):
        errors.append("duplicate order_item product")
    pay_by_order = {p["order_id"]: p for p in d.payments}
    for o in d.orders:
        if o["user_id"] not in user_ids: errors.append("order orphan user")
        lines = items_by_order.get(o["order_id"], [])
        if not lines: errors.append(f"order {o['order_id']} has no items")
        if sum(l["line_total"] for l in lines) != o["subtotal"]: errors.append(f"order {o['order_id']} subtotal mismatch")
        if o["total_amount"] != o["subtotal"] + o["shipping_fee"]: errors.append("order total mismatch")
        if o["shipping_fee"] != shipping_fee(o["subtotal"]): errors.append("shipping fee rule violated")
        pay = pay_by_order.get(o["order_id"])
        if not pay or pay["amount"] != o["total_amount"]: errors.append(f"order {o['order_id']} payment mismatch")
        if o["status"] == "CANCELLED" and pay["status"] not in ("REFUNDED", "FAILED"): errors.append("cancelled order payment status")
        if o["status"] != "CANCELLED" and pay["status"] in ("REFUNDED", "FAILED"): errors.append("live order with failed payment")
    if len({o["order_ref"] for o in d.orders}) != len(d.orders): errors.append("duplicate order_ref")
    if len({r["order_id"] for r in d.payments}) != len(d.payments): errors.append("duplicate payment per order")
    if len({(r["product_id"], r["user_id"]) for r in d.reviews}) != len(d.reviews): errors.append("duplicate review")
    for r in d.reviews:
        if not 1 <= r["rating"] <= 5: errors.append("rating range")
        if r["product_id"] not in prod_ids or r["user_id"] not in user_ids: errors.append("review orphan")
    for ci in d.cart_items:
        if ci["cart_id"] not in cart_ids or ci["product_id"] not in prod_ids: errors.append("cart_item orphan")
    active_per_user = {}
    for c in d.carts:
        if c["status"] == "ACTIVE":
            active_per_user[c["user_id"]] = active_per_user.get(c["user_id"], 0) + 1
    if any(v > 1 for v in active_per_user.values()): errors.append("user with two active carts")

    # Eco Swap coverage: at least 10 products must have a qualifying swap
    swaps = eco_swap_pairs(d)
    if len(swaps) < 10: errors.append(f"only {len(swaps)} eco-swap source products")
    return errors


def eco_swap_pairs(d: Dataset, tolerance=0.20):
    sust = {s["product_id"]: s["eco_score"] for s in d.sustainability}
    result = {}
    for o in d.products:
        if o["product_id"] not in sust:
            continue
        for a in d.products:
            if (a["category_id"] == o["category_id"] and a["product_id"] != o["product_id"]
                    and a["product_id"] in sust and sust[a["product_id"]] > sust[o["product_id"]]
                    and o["price"] * Decimal(1 - tolerance) <= a["price"] <= o["price"] * Decimal(1 + tolerance)
                    and a["stock_quantity"] > 0):
                result.setdefault(o["product_id"], []).append(a["product_id"])
    return result


# --------------------------------------------------------------------------------
# Table / column metadata (shared by the SQL writer and the Oracle loader)
# --------------------------------------------------------------------------------
TABLES = [
    ("category", "pk_category", ["category_id", "category_name", "slug", "description", "icon"], "categories"),
    ("app_user", "pk_app_user", ["user_id", "full_name", "email", "password_hash", "phone", "address_line", "city",
                                 "state", "pincode", "role", "is_demo", "data_origin", "created_at"], "users"),
    ("product", "pk_product", ["product_id", "category_id", "product_name", "brand", "description", "price",
                               "stock_quantity", "image_url", "is_active", "is_featured", "data_origin", "source_key",
                               "created_at"], "products"),
    ("product_sustainability", "pk_sustainability",
     ["sustainability_id", "product_id", "material", "packaging_type", "recyclability_pct", "eco_score",
      "carbon_footprint_kg", "carbon_footprint_unit", "sustainability_explanation", "score_source", "data_origin",
      "updated_at"], "sustainability"),
    ("cart", "pk_cart", ["cart_id", "user_id", "status", "created_at", "updated_at"], "carts"),
    ("cart_item", "pk_cart_item", ["cart_item_id", "cart_id", "product_id", "quantity", "added_at"], "cart_items"),
    ("customer_order", "pk_customer_order",
     ["order_id", "order_ref", "user_id", "order_date", "status", "subtotal", "shipping_fee", "total_amount",
      "shipping_address", "data_origin", "source_key"], "orders"),
    ("order_item", "pk_order_item", ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "line_total"],
     "order_items"),
    ("payment", "pk_payment", ["payment_id", "order_id", "payment_method", "amount", "status", "transaction_ref",
                               "paid_at", "created_at"], "payments"),
    ("review", "pk_review", ["review_id", "product_id", "user_id", "rating", "title", "review_text", "is_verified",
                             "data_origin", "created_at"], "reviews"),
]
ID_COLUMN = {"category": "category_id", "app_user": "user_id", "product": "product_id",
             "product_sustainability": "sustainability_id", "cart": "cart_id", "cart_item": "cart_item_id",
             "customer_order": "order_id", "order_item": "order_item_id", "payment": "payment_id", "review": "review_id"}


def insert_sql(table, pk_index, cols, binds=False):
    vals = ", ".join(f":{c}" for c in cols) if binds else "{values}"
    return (f"INSERT /*+ IGNORE_ROW_ON_DUPKEY_INDEX({table}, {pk_index}) */ INTO {table} "
            f"({', '.join(cols)}) VALUES ({vals})")


def sql_literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, Decimal)):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, dt.datetime):
        return f"TIMESTAMP '{v:%Y-%m-%d %H:%M:%S}'"
    s = str(v).replace("'", "''")
    return f"'{s}'"


def write_sql(d: Dataset, path: str):
    out = []
    out.append("-- =============================================================================")
    out.append("-- EcoCart | 05_seed_data.sql  (run as ECOCART)   *** GENERATED FILE ***")
    out.append("-- Generated by scripts/seed_data.py --sql ; do not edit by hand.")
    out.append("-- Real-world product names/brands; static illustrative prices/stock; synthetic customers/orders,")
    out.append("-- illustrative Eco-Scores from assumed attributes, not certified measurements. Not real purchases or")
    out.append("-- certified environmental measurements. Safe to re-run: duplicates are ignored.")
    out.append("-- =============================================================================")
    out.append("SET DEFINE OFF")
    for table, pk, cols, attr in TABLES:
        rows = getattr(d, attr)
        out.append(f"\n-- ---- {table} ({len(rows)} rows) ----")
        stmt = insert_sql(table, pk, cols)
        for r in rows:
            out.append(stmt.format(values=", ".join(sql_literal(r[c]) for c in cols)) + ";")
        out.append("COMMIT;")
    out.append("\n-- Move every IDENTITY sequence past the highest seeded key so live inserts never collide.")
    for table, _, _, _ in TABLES:
        out.append(f"ALTER TABLE {table} MODIFY ({ID_COLUMN[table]} GENERATED BY DEFAULT ON NULL AS IDENTITY (START WITH LIMIT VALUE));")
    out.append("COMMIT;")
    out.append("\nPROMPT Seed data loaded.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def load_oracle(d: Dataset):
    from ecocart.db import get_connection  # noqa
    import oracledb
    conn = get_connection()
    report = {}
    try:
        cur = conn.cursor()
        for table, pk, cols, attr in TABLES:
            rows = getattr(d, attr)
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            before = cur.fetchone()[0]
            data = [{c: (float(r[c]) if isinstance(r[c], Decimal) else r[c]) for c in cols} for r in rows]
            cur.executemany(insert_sql(table, pk, cols, binds=True), data)
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            after = cur.fetchone()[0]
            report[table] = (len(rows), after - before, after)
        for table, _, _, _ in TABLES:
            cur.execute(f"ALTER TABLE {table} MODIFY ({ID_COLUMN[table]} GENERATED BY DEFAULT ON NULL AS IDENTITY (START WITH LIMIT VALUE))")
        conn.commit()
    except oracledb.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sql", action="store_true", help="write db/05_seed_data.sql")
    ap.add_argument("--load", action="store_true", help="insert into Oracle using .env settings")
    ap.add_argument("--validate", action="store_true", help="run dataset consistency checks")
    args = ap.parse_args()
    if not (args.sql or args.load or args.validate):
        ap.print_help(); return 1

    from werkzeug.security import generate_password_hash
    d = generate(generate_password_hash)
    counts = {attr: len(getattr(d, attr)) for _, _, _, attr in TABLES}
    print("Generated:", counts)
    swaps = eco_swap_pairs(d)
    print(f"Eco Swap coverage: {len(swaps)} products have at least one qualifying alternative")

    if args.validate or args.sql or args.load:
        errs = validate(d)
        if errs:
            print("VALIDATION FAILED:"); [print("  -", e) for e in errs]; return 2
        print("Validation: OK")
    if args.sql:
        path = os.path.join(ROOT, "db", "05_seed_data.sql")
        write_sql(d, path)
        print("Wrote", path)
    if args.load:
        rep = load_oracle(d)
        print(f"{'table':24} {'generated':>9} {'inserted':>9} {'now in db':>9}")
        for t, (g, ins, tot) in rep.items():
            print(f"{t:24} {g:9} {ins:9} {tot:9}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
