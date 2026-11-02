#!/usr/bin/env python3
"""
Import the ORIGINAL "Indian E-Commerce Sales & Customer Analytics" CSV files
(when available) into the existing ECOCART schema.

    python scripts/import_dataset.py --dir data/original            # import
    python scripts/import_dataset.py --dir data/original --dry-run  # validate + report only

Expected files (any missing file is reported and that part is skipped - the
run never aborts because a file is absent):
    customers.csv   -> APP_USER      (DATA_ORIGIN = 'ORIGINAL')
    products.csv    -> CATEGORY, PRODUCT
    orders.csv      -> CUSTOMER_ORDER, PAYMENT
    order_items.csv -> ORDER_ITEM   (optional; if absent, orders with a product
                                     column are imported as single-line orders)

Column names differ between dataset versions, so each logical field is matched
against a list of candidate header names (see FIELD_CANDIDATES) and can be
overridden with --mapping mapping.json ({"customer_id": "CustomerID", ...}).

Idempotency: every imported row stores its source key (SOURCE_KEY / EMAIL /
ORDER_REF = 'ORIG-<id>'), and rows whose key already exists are skipped, so the
importer can be re-run safely. Original rows are never mixed with the
synthetic demo rows: they are distinguishable by DATA_ORIGIN = 'ORIGINAL'.

What this importer refuses to do:
  * invent customers for orders whose customer is missing (such orders are
    rejected and counted),
  * invent sustainability data for original products (they appear in the
    "missing sustainability data" report until assessed),
  * expose real personal data - original customer e-mails are replaced by a
    deterministic pseudonymous address (orig-<id>@example.com) and the
    password is an unusable random hash, because imported customers are
    analytics records, not login accounts.
"""
import argparse
import csv
import json
import os
import re
import secrets
import sys
from decimal import Decimal, InvalidOperation
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FIELD_CANDIDATES = {
    # customers.csv
    "customer_id": ["customer_id", "customerid", "cust_id", "id", "customer id"],
    "customer_name": ["customer_name", "name", "full_name", "customername", "customer"],
    "city": ["city", "customer_city"],
    "state": ["state", "customer_state", "region"],
    "pincode": ["pincode", "pin_code", "postal_code", "zip"],
    # products.csv
    "product_id": ["product_id", "productid", "sku", "id", "product id"],
    "product_name": ["product_name", "productname", "name", "product", "item_name"],
    "category": ["category", "product_category", "category_name", "sub_category"],
    "brand": ["brand", "brand_name"],
    "price": ["price", "unit_price", "selling_price", "mrp", "amount"],
    "stock": ["stock", "stock_quantity", "quantity_available", "inventory"],
    # orders.csv
    "order_id": ["order_id", "orderid", "id", "order id", "invoice_no"],
    "order_date": ["order_date", "orderdate", "date", "order date", "purchase_date"],
    "order_status": ["status", "order_status", "delivery_status"],
    "payment_method": ["payment_method", "payment_mode", "paymentmethod", "payment"],
    "total": ["total", "total_amount", "order_total", "sales", "amount", "grand_total"],
    "quantity": ["quantity", "qty", "units"],
}
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M", "%Y/%m/%d"]

STATUS_MAP = {"delivered": "DELIVERED", "shipped": "SHIPPED", "cancelled": "CANCELLED", "canceled": "CANCELLED",
              "returned": "CANCELLED", "pending": "PLACED", "processing": "CONFIRMED", "confirmed": "CONFIRMED",
              "placed": "PLACED", "completed": "DELIVERED"}
PAY_MAP = {"cod": "COD", "cash on delivery": "COD", "cash": "COD", "upi": "DEMO_UPI", "card": "DEMO_CARD",
           "credit card": "DEMO_CARD", "debit card": "DEMO_CARD", "net banking": "DEMO_CARD", "wallet": "DEMO_WALLET",
           "emi": "DEMO_CARD"}


class Report:
    def __init__(self):
        self.counts = {}
        self.rejected = {}

    def ok(self, table): self.counts[table] = self.counts.get(table, 0) + 1
    def reject(self, table, reason): self.rejected.setdefault(table, {}).setdefault(reason, 0); self.rejected[table][reason] += 1

    def __str__(self):
        lines = ["Imported rows:"] + [f"  {t:18} {n}" for t, n in self.counts.items()] or ["  (none)"]
        lines.append("Rejected rows:")
        if not self.rejected:
            lines.append("  (none)")
        for t, reasons in self.rejected.items():
            for r, n in reasons.items():
                lines.append(f"  {t:18} {n:5}  {r}")
        return "\n".join(lines)


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return rows


def resolve(headers, field, mapping):
    if field in mapping:
        return mapping[field]
    norm = {re.sub(r"[^a-z0-9]", "", h.lower()): h for h in headers}
    for cand in FIELD_CANDIDATES[field]:
        key = re.sub(r"[^a-z0-9]", "", cand)
        if key in norm:
            return norm[key]
    return None


def parse_money(v):
    try:
        return Decimal(str(v).replace(",", "").replace("₹", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None


def parse_date(v):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(v).strip(), fmt)
        except ValueError:
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=os.path.join(ROOT, "data", "original"))
    ap.add_argument("--mapping", help="JSON file overriding column names")
    ap.add_argument("--dry-run", action="store_true", help="validate and report without writing to Oracle")
    args = ap.parse_args()

    mapping = json.load(open(args.mapping)) if args.mapping else {}
    files = {n: os.path.join(args.dir, f"{n}.csv") for n in ("customers", "products", "orders", "order_items")}
    present = {n: os.path.exists(p) for n, p in files.items()}
    print("Dataset directory:", args.dir)
    for n, p in files.items():
        print(f"  {n + '.csv':18} {'found' if present[n] else 'MISSING'}")
    if not any(present.values()):
        print("\nNo original dataset files found. Nothing to import - the synthetic demo dataset "
              "(scripts/seed_data.py) keeps the application fully demonstrable.")
        return 0

    rep = Report()
    conn = None
    cur = None
    if not args.dry_run:
        from ecocart.db import get_connection
        conn = get_connection()
        cur = conn.cursor()

    def exists(sql, **binds):
        if cur is None:
            return False
        cur.execute(sql, binds)
        return cur.fetchone() is not None

    # ---------------- customers ----------------
    cust_ids = set()
    if present["customers"]:
        rows = read_csv(files["customers"])
        h = rows[0].keys() if rows else []
        c_id, c_name = resolve(h, "customer_id", mapping), resolve(h, "customer_name", mapping)
        c_city, c_state, c_pin = resolve(h, "city", mapping), resolve(h, "state", mapping), resolve(h, "pincode", mapping)
        if not c_id:
            print("customers.csv: cannot find a customer id column; skipped")
        for r in rows:
            cid = (r.get(c_id) or "").strip()
            if not cid:
                rep.reject("app_user", "missing customer id"); continue
            email = f"orig-{re.sub(r'[^A-Za-z0-9]', '', cid).lower()}@example.com"
            cust_ids.add(cid)
            if exists("SELECT 1 FROM app_user WHERE email = :e", e=email):
                rep.reject("app_user", "already imported"); continue
            if cur:
                cur.execute("""INSERT INTO app_user (full_name, email, password_hash, city, state, pincode, role, is_demo, data_origin)
                               VALUES (:n, :e, :p, :c, :s, :z, 'CUSTOMER', 0, 'ORIGINAL')""",
                            n=(r.get(c_name) or f"Customer {cid}")[:120], e=email, p="!unusable-" + secrets.token_hex(16),
                            c=(r.get(c_city) or None), s=(r.get(c_state) or None), z=(r.get(c_pin) or None))
            rep.ok("app_user")

    # ---------------- products ----------------
    prod_ids = set()
    if present["products"]:
        rows = read_csv(files["products"])
        h = rows[0].keys() if rows else []
        p_id, p_name = resolve(h, "product_id", mapping), resolve(h, "product_name", mapping)
        p_cat, p_brand, p_price, p_stock = (resolve(h, k, mapping) for k in ("category", "brand", "price", "stock"))
        for r in rows:
            pid, name = (r.get(p_id) or "").strip(), (r.get(p_name) or "").strip()
            price = parse_money(r.get(p_price)) if p_price else None
            if not pid or not name:
                rep.reject("product", "missing id or name"); continue
            if price is None or price <= 0:
                rep.reject("product", "invalid price"); continue
            prod_ids.add(pid)
            key = f"ORIG-{pid}"
            if exists("SELECT 1 FROM product WHERE source_key = :k", k=key):
                rep.reject("product", "already imported"); continue
            cat_name = (r.get(p_cat) or "Uncategorised").strip()[:80] if p_cat else "Uncategorised"
            if cur:
                slug = re.sub(r"[^a-z0-9]+", "-", cat_name.lower()).strip("-")[:80]
                cur.execute("SELECT category_id FROM category WHERE category_name = :n", n=cat_name)
                row = cur.fetchone()
                if row:
                    cat_id = row[0]
                else:
                    out = cur.var(int)
                    cur.execute("INSERT INTO category (category_name, slug, description) VALUES (:n, :s, :d) RETURNING category_id INTO :o",
                                n=cat_name, s=slug, d="Imported from the original dataset.", o=out)
                    cat_id = out.getvalue()[0]
                    rep.ok("category")
                stock = int(float(r.get(p_stock) or 0)) if p_stock else 0
                cur.execute("""INSERT INTO product (category_id, product_name, brand, description, price, stock_quantity,
                               image_url, is_active, data_origin, source_key)
                               VALUES (:c, :n, :b, :d, :p, :s, '/static/img/placeholder.svg', 1, 'ORIGINAL', :k)""",
                            c=cat_id, n=name[:160], b=(r.get(p_brand) or None), d="Imported from the original dataset; sustainability not yet assessed.",
                            p=float(price), s=max(0, stock), k=key)
            rep.ok("product")

    # ---------------- orders (+ items + payments) ----------------
    if present["orders"]:
        rows = read_csv(files["orders"])
        h = rows[0].keys() if rows else []
        o_id, o_cust, o_date = resolve(h, "order_id", mapping), resolve(h, "customer_id", mapping), resolve(h, "order_date", mapping)
        o_status, o_pay, o_total = resolve(h, "order_status", mapping), resolve(h, "payment_method", mapping), resolve(h, "total", mapping)
        o_prod, o_qty, o_price = resolve(h, "product_id", mapping), resolve(h, "quantity", mapping), resolve(h, "price", mapping)
        items_by_order = {}
        if present["order_items"]:
            irows = read_csv(files["order_items"])
            ih = irows[0].keys() if irows else []
            i_order, i_prod, i_qty, i_price = (resolve(ih, k, mapping) for k in ("order_id", "product_id", "quantity", "price"))
            for ir in irows:
                items_by_order.setdefault((ir.get(i_order) or "").strip(), []).append(
                    ((ir.get(i_prod) or "").strip(), ir.get(i_qty), ir.get(i_price)))
        for r in rows:
            oid = (r.get(o_id) or "").strip()
            cid = (r.get(o_cust) or "").strip() if o_cust else ""
            if not oid:
                rep.reject("customer_order", "missing order id"); continue
            if not cid or (cust_ids and cid not in cust_ids):
                rep.reject("customer_order", "customer not found (customers.csv missing or id unknown)"); continue
            odate = parse_date(r.get(o_date)) if o_date else None
            if odate is None:
                rep.reject("customer_order", "unparseable order date"); continue
            items = items_by_order.get(oid) or ([( (r.get(o_prod) or "").strip(), r.get(o_qty) or 1, r.get(o_price))] if o_prod else [])
            lines = []
            for (pid, qty, price) in items:
                try:
                    q = int(float(qty))
                except (TypeError, ValueError):
                    q = 0
                up = parse_money(price)
                if not pid or q <= 0 or (prod_ids and pid not in prod_ids):
                    continue
                lines.append((pid, q, up))
            if not lines:
                rep.reject("customer_order", "no valid order lines"); continue
            ref = f"ORIG-{oid}"[:30]
            if exists("SELECT 1 FROM customer_order WHERE order_ref = :r", r=ref):
                rep.reject("customer_order", "already imported"); continue
            status = STATUS_MAP.get((r.get(o_status) or "delivered").strip().lower(), "DELIVERED")
            method = PAY_MAP.get((r.get(o_pay) or "cod").strip().lower(), "COD")
            if cur:
                cur.execute("SELECT user_id FROM app_user WHERE email = :e", e=f"orig-{re.sub(r'[^A-Za-z0-9]', '', cid).lower()}@example.com")
                urow = cur.fetchone()
                if not urow:
                    rep.reject("customer_order", "customer not in database"); continue
                resolved = []
                for pid, q, up in lines:
                    cur.execute("SELECT product_id, price FROM product WHERE source_key = :k", k=f"ORIG-{pid}")
                    prow = cur.fetchone()
                    if not prow:
                        continue
                    unit = up if up is not None else Decimal(str(prow[1]))
                    resolved.append((prow[0], q, unit))
                if not resolved:
                    rep.reject("customer_order", "products not in database"); continue
                subtotal = sum((u * q for _, q, u in resolved), Decimal("0"))
                total = parse_money(r.get(o_total)) if o_total else None
                ship = (total - subtotal) if total is not None and total >= subtotal else Decimal("0")
                out = cur.var(int)
                cur.execute("""INSERT INTO customer_order (order_ref, user_id, order_date, status, subtotal, shipping_fee, total_amount, data_origin, source_key)
                               VALUES (:r, :u, :d, :s, :st, :sh, :t, 'ORIGINAL', :k) RETURNING order_id INTO :o""",
                            r=ref, u=urow[0], d=odate, s=status, st=float(subtotal), sh=float(ship), t=float(subtotal + ship), k=oid[:80], o=out)
                new_id = out.getvalue()[0]
                seen = set()
                for prod_id, q, unit in resolved:
                    if prod_id in seen:
                        continue  # UQ(order_id, product_id)
                    seen.add(prod_id)
                    cur.execute("INSERT INTO order_item (order_id, product_id, quantity, unit_price, line_total) VALUES (:o, :p, :q, :u, :l)",
                                o=new_id, p=prod_id, q=q, u=float(unit), l=float(unit * q))
                    rep.ok("order_item")
                pay_status = "REFUNDED" if status == "CANCELLED" and method != "COD" else ("FAILED" if status == "CANCELLED" else "PAID")
                cur.execute("INSERT INTO payment (order_id, payment_method, amount, status, paid_at) VALUES (:o, :m, :a, :s, :d)",
                            o=new_id, m=method, a=float(subtotal + ship), s=pay_status, d=(odate if pay_status != "FAILED" else None))
                rep.ok("payment")
            rep.ok("customer_order")

    if conn:
        conn.commit()
        conn.close()
    print("\n" + ("DRY RUN - nothing written.\n" if args.dry_run else "") + str(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
