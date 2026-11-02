"""
Test fixtures.

Two kinds of tests live here:
  * route/template/logic tests (always run): the Oracle service layer is replaced by
    an in-memory fake built from the SAME generated demo dataset, so every page,
    form, filter and authorization path is exercised without a database.
  * Oracle integration tests (tests/test_oracle_integration.py): run only when a
    live ECOCART database is reachable via .env; otherwise skipped with a notice.
"""
import os
import sys
from datetime import datetime
from decimal import Decimal

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from werkzeug.security import generate_password_hash  # noqa: E402

from config import TestConfig  # noqa: E402
from ecocart import create_app  # noqa: E402
from ecocart.db import DBError  # noqa: E402
from ecocart.eco_methodology import eco_grade  # noqa: E402
from ecocart.services import analytics, cart, catalog, ecoswap, orders, reviews, users  # noqa: E402
from seed_data import generate, shipping_fee  # noqa: E402

PW_HASH_CACHE = {}


def _hash(pw):
    if pw not in PW_HASH_CACHE:
        PW_HASH_CACHE[pw] = generate_password_hash(pw, method="scrypt", salt_length=8)
    return PW_HASH_CACHE[pw]


class FakeStore:
    """In-memory stand-in for the Oracle tables, loaded from the generated demo dataset."""

    def __init__(self):
        d = generate(_hash)
        self.d = d
        self.categories = {c["category_id"]: c for c in d.categories}
        self.users = {u["user_id"]: u for u in d.users}
        self.products = {p["product_id"]: p for p in d.products}
        self.sust = {s["product_id"]: s for s in d.sustainability}
        self.reviews = list(d.reviews)
        self.orders = {o["order_id"]: o for o in d.orders}
        self.order_items = list(d.order_items)
        self.payments = {p["order_id"]: p for p in d.payments}
        self.carts = {c["cart_id"]: c for c in d.carts}
        self.cart_items = list(d.cart_items)
        self.next_ids = dict(user=max(self.users) + 1, order=max(self.orders) + 1, cart=max(self.carts) + 1,
                             review=len(self.reviews) + 1)

    # ---- catalogue rows shaped like V_PRODUCT_CATALOG ----
    def catalog_row(self, pid):
        p = self.products[pid]
        c = self.categories[p["category_id"]]
        s = self.sust.get(pid, {})
        rv = [r for r in self.reviews if r["product_id"] == pid]
        avg = round(sum(r["rating"] for r in rv) / len(rv), 2) if rv else None
        row = dict(p)
        row.update(category_name=c["category_name"], category_slug=c["slug"],
                   eco_score=s.get("eco_score"), material=s.get("material"), packaging_type=s.get("packaging_type"),
                   recyclability_pct=s.get("recyclability_pct"), carbon_footprint_kg=s.get("carbon_footprint_kg"),
                   carbon_footprint_unit=s.get("carbon_footprint_unit"),
                   sustainability_explanation=s.get("sustainability_explanation"), score_source=s.get("score_source"),
                   sustainability_origin=s.get("data_origin"), eco_grade=eco_grade(s.get("eco_score")),
                   review_count=len(rv) or None, avg_rating=avg)
        return row

    def all_rows(self):
        return [self.catalog_row(pid) for pid in self.products]


def install_fake_services(store: FakeStore, monkeypatch):
    S = store

    # ---------- catalog ----------
    def list_products(page=1, page_size=12, sort="featured", q=None, category=None, min_price=None, max_price=None,
                      min_eco=None, max_eco=None, in_stock=False, has_eco=False):
        rows = [r for r in S.all_rows() if r["is_active"] == 1]
        if q: rows = [r for r in rows if q.lower() in r["product_name"].lower()]
        if category: rows = [r for r in rows if r["category_slug"] == category]
        if min_price is not None: rows = [r for r in rows if float(r["price"]) >= min_price]
        if max_price is not None: rows = [r for r in rows if float(r["price"]) <= max_price]
        if min_eco is not None: rows = [r for r in rows if r["eco_score"] is not None and r["eco_score"] >= min_eco]
        if max_eco is not None: rows = [r for r in rows if r["eco_score"] is not None and r["eco_score"] <= max_eco]
        if in_stock: rows = [r for r in rows if r["stock_quantity"] > 0]
        if has_eco: rows = [r for r in rows if r["eco_score"] is not None]
        key = {"price_asc": lambda r: float(r["price"]), "price_desc": lambda r: -float(r["price"]),
               "eco_desc": lambda r: -(r["eco_score"] if r["eco_score"] is not None else -1),
               "eco_asc": lambda r: (r["eco_score"] if r["eco_score"] is not None else 999),
               "rating": lambda r: -(r["avg_rating"] or 0), "name": lambda r: r["product_name"],
               "newest": lambda r: -r["product_id"]}.get(sort, lambda r: (-r["is_featured"], -(r["eco_score"] or 0)))
        rows.sort(key=key)
        total = len(rows); start = (page - 1) * page_size
        return dict(items=rows[start:start + page_size], total=total, page=page,
                    pages=max(1, (total + page_size - 1) // page_size), page_size=page_size)

    monkeypatch.setattr(catalog, "list_products", list_products)
    monkeypatch.setattr(catalog, "get_product", lambda pid: S.catalog_row(pid) if pid in S.products else None)
    monkeypatch.setattr(catalog, "featured_products", lambda limit=8: [r for r in S.all_rows() if r["is_featured"]][:limit])
    monkeypatch.setattr(catalog, "top_sustainable", lambda limit=8: sorted([r for r in S.all_rows() if r["eco_score"]], key=lambda r: -r["eco_score"])[:limit])

    def categories_with_counts():
        out = []
        for c in S.categories.values():
            ps = [S.catalog_row(p) for p in S.products if S.products[p]["category_id"] == c["category_id"]]
            scored = [p["eco_score"] for p in ps if p["eco_score"] is not None]
            out.append(dict(c, product_count=len(ps), avg_eco_score=round(sum(scored) / len(scored)) if scored else None,
                            min_price=min(p["price"] for p in ps) if ps else None))
        return sorted(out, key=lambda c: c["category_name"])
    monkeypatch.setattr(catalog, "categories_with_counts", categories_with_counts)
    monkeypatch.setattr(catalog, "get_category", lambda slug: next((c for c in S.categories.values() if c["slug"] == slug), None))
    monkeypatch.setattr(catalog, "price_bounds", lambda: dict(min_price=min(p["price"] for p in S.products.values()), max_price=max(p["price"] for p in S.products.values())))
    monkeypatch.setattr(catalog, "home_stats", lambda: dict(products=len(S.products), categories=len(S.categories), scored=len(S.sust),
                                                             avg_eco=round(sum(s["eco_score"] for s in S.sust.values()) / len(S.sust), 1),
                                                             good_or_better=sum(1 for s in S.sust.values() if s["eco_score"] >= 65), orders=len(S.orders)))

    # ---------- eco swap (same rules as ECOCART_PKG.ECO_SWAP) ----------
    def recommendations(product_id, tolerance=None, max_rows=None):
        tol = 0.20 if tolerance is None else float(tolerance)
        lim = 4 if max_rows is None else max_rows
        o = S.catalog_row(product_id)
        alts = []
        for a in S.all_rows():
            if (a["category_id"] == o["category_id"] and a["product_id"] != product_id and a["eco_score"] is not None
                    and a["eco_score"] > o["eco_score"] and a["stock_quantity"] > 0 and a["is_active"] == 1
                    and float(o["price"]) * (1 - tol) <= float(a["price"]) <= float(o["price"]) * (1 + tol)):
                a = dict(a, score_gain=a["eco_score"] - o["eco_score"], price_diff=float(a["price"]) - float(o["price"]),
                         price_diff_pct=round((float(a["price"]) - float(o["price"])) / float(o["price"]) * 100, 1))
                a["reasons"] = ecoswap._reasons(a, tol)
                alts.append(a)
        alts.sort(key=lambda a: (-a["eco_score"], abs(a["price_diff"])))
        return alts[:lim], tol
    monkeypatch.setattr(ecoswap, "recommendations", recommendations)

    def swap_showcase(limit=6):
        out = []
        for pid in S.products:
            if pid not in S.sust: continue
            alts, _ = recommendations(pid)
            if alts:
                o, a = S.catalog_row(pid), alts[0]
                out.append(dict(orig_id=pid, orig_name=o["product_name"], orig_price=o["price"], orig_score=o["eco_score"], orig_image=o["image_url"],
                                category_name=o["category_name"], alt_id=a["product_id"], alt_name=a["product_name"], alt_price=a["price"],
                                alt_score=a["eco_score"], alt_image=a["image_url"], score_gain=a["score_gain"], price_diff=a["price_diff"]))
        out.sort(key=lambda s: -s["score_gain"])
        return out[:limit]
    monkeypatch.setattr(ecoswap, "swap_showcase", swap_showcase)

    # ---------- users ----------
    def get_by_email(email):
        return next((dict(u) for u in S.users.values() if u["email"].lower() == email.strip().lower()), None)
    monkeypatch.setattr(users, "get_by_email", get_by_email)
    monkeypatch.setattr(users, "get_by_id", lambda uid: dict(S.users[uid]) if uid in S.users else None)

    def register(full_name, email, password, phone=None, city=None):
        from ecocart.security import validate_email, validate_password
        if len((full_name or "").strip()) < 2: raise DBError("Please enter your name.")
        err = validate_email(email) or validate_password(password or "")
        if err: raise DBError(err)
        if get_by_email(email): raise DBError("An account with this e-mail already exists. Try signing in.")
        uid = S.next_ids["user"]; S.next_ids["user"] += 1
        S.users[uid] = dict(user_id=uid, full_name=full_name.strip(), email=email.strip().lower(), password_hash=_hash(password),
                            phone=phone, address_line=None, city=city, state=None, pincode=None, role="CUSTOMER", is_demo=0,
                            data_origin="LIVE", created_at=datetime.now())
        return dict(S.users[uid])
    monkeypatch.setattr(users, "register", register)

    def authenticate(email, password):
        from ecocart.security import verify_password
        u = get_by_email(email or "")
        return u if u and verify_password(u["password_hash"], password or "") else None
    monkeypatch.setattr(users, "authenticate", authenticate)
    monkeypatch.setattr(users, "update_profile", lambda uid, n, ph, a, c, s, z: S.users[uid].update(full_name=n, phone=ph, address_line=a, city=c, state=s, pincode=z))

    # ---------- cart ----------
    def active_cart(uid, create=False):
        for c in S.carts.values():
            if c["user_id"] == uid and c["status"] == "ACTIVE": return c["cart_id"]
        if not create: return None
        cid = S.next_ids["cart"]; S.next_ids["cart"] += 1
        S.carts[cid] = dict(cart_id=cid, user_id=uid, status="ACTIVE"); return cid

    def get_cart(uid):
        cid = active_cart(uid)
        items = []
        for ci in S.cart_items:
            if ci["cart_id"] == cid:
                p = S.catalog_row(ci["product_id"])
                items.append(dict(cart_item_id=ci["cart_item_id"], product_id=p["product_id"], quantity=ci["quantity"], product_name=p["product_name"],
                                  brand=p["brand"], price=p["price"], image_url=p["image_url"], stock_quantity=p["stock_quantity"], is_active=1,
                                  eco_score=p["eco_score"], line_total=float(p["price"]) * ci["quantity"]))
        subtotal = sum(i["line_total"] for i in items)
        shipping = 0.0 if subtotal >= 999 or not items else 49.0
        return dict(cart_id=cid, items=items, count=sum(i["quantity"] for i in items), subtotal=subtotal, shipping=shipping,
                    total=subtotal + shipping, problems=[i for i in items if i["stock_quantity"] < i["quantity"]])
    monkeypatch.setattr(cart, "get_cart", get_cart)
    monkeypatch.setattr(cart, "item_count", lambda uid: get_cart(uid)["count"])

    def add_item(uid, pid, qty=1):
        qty = cart._check_qty(qty)
        p = S.products.get(pid)
        if not p: raise DBError("That product is not available.")
        cid = active_cart(uid, create=True)
        for ci in S.cart_items:
            if ci["cart_id"] == cid and ci["product_id"] == pid:
                if ci["quantity"] + qty > p["stock_quantity"]: raise DBError(f"Only {p['stock_quantity']} unit(s) of {p['product_name']} are in stock.")
                ci["quantity"] += qty; return p["product_name"]
        if qty > p["stock_quantity"]: raise DBError(f"Only {p['stock_quantity']} unit(s) of {p['product_name']} are in stock.")
        S.cart_items.append(dict(cart_item_id=len(S.cart_items) + 1, cart_id=cid, product_id=pid, quantity=qty))
        return p["product_name"]
    monkeypatch.setattr(cart, "add_item", add_item)

    def update_item(uid, pid, qty):
        qty = cart._check_qty(qty)
        cid = active_cart(uid)
        p = S.products[pid]
        if qty > p["stock_quantity"]: raise DBError(f"Only {p['stock_quantity']} unit(s) of {p['product_name']} are in stock.")
        for ci in S.cart_items:
            if ci["cart_id"] == cid and ci["product_id"] == pid: ci["quantity"] = qty; return
        raise DBError("That item is not in your cart.")
    monkeypatch.setattr(cart, "update_item", update_item)

    def remove_item(uid, pid):
        cid = active_cart(uid)
        S.cart_items[:] = [ci for ci in S.cart_items if not (ci["cart_id"] == cid and ci["product_id"] == pid)]
    monkeypatch.setattr(cart, "remove_item", remove_item)

    # ---------- orders (mirrors ECOCART_PKG.PLACE_ORDER semantics) ----------
    def place_order(uid, method, address, simulate_failure=False):
        if method not in orders.METHOD_KEYS: raise DBError("Please choose a valid payment method.")
        if len((address or "").strip()) < 10: raise DBError("Please enter a complete shipping address.")
        c = get_cart(uid)
        if not c["items"]: raise DBError("Your cart is empty.")
        for i in c["items"]:
            if i["quantity"] > i["stock_quantity"]: raise DBError(f"Only {i['stock_quantity']} unit(s) of {i['product_name']} left in stock.")
        if method != "COD" and simulate_failure: raise DBError("Demo payment declined by simulated gateway.")
        oid = S.next_ids["order"]; S.next_ids["order"] += 1
        subtotal = Decimal(str(round(c["subtotal"], 2))); ship = shipping_fee(subtotal)
        ref = f"EC-TEST-{oid:06d}"
        S.orders[oid] = dict(order_id=oid, order_ref=ref, user_id=uid, order_date=datetime.now(), status="PLACED" if method == "COD" else "CONFIRMED",
                             subtotal=subtotal, shipping_fee=ship, total_amount=subtotal + ship, shipping_address=address, data_origin="LIVE")
        for i in c["items"]:
            S.order_items.append(dict(order_item_id=len(S.order_items) + 1, order_id=oid, product_id=i["product_id"], quantity=i["quantity"],
                                      unit_price=i["price"], line_total=Decimal(str(i["line_total"]))))
            S.products[i["product_id"]]["stock_quantity"] -= i["quantity"]
        S.payments[oid] = dict(payment_id=oid, order_id=oid, payment_method=method, amount=subtotal + ship,
                               status="PENDING" if method == "COD" else "PAID", transaction_ref=None if method == "COD" else f"DEMO-{ref}",
                               paid_at=None if method == "COD" else datetime.now())
        S.carts[c["cart_id"]]["status"] = "CHECKED_OUT"
        return oid, ref
    monkeypatch.setattr(orders, "place_order", place_order)

    def summary_row(o):
        pay = S.payments[o["order_id"]]; u = S.users[o["user_id"]]
        its = [i for i in S.order_items if i["order_id"] == o["order_id"]]
        return dict(order_id=o["order_id"], order_ref=o["order_ref"], user_id=o["user_id"], customer_name=u["full_name"], customer_email=u["email"],
                    order_date=o["order_date"], order_status=o["status"], subtotal=o["subtotal"], shipping_fee=o["shipping_fee"],
                    total_amount=o["total_amount"], data_origin=o["data_origin"], item_lines=len(its), item_units=sum(i["quantity"] for i in its),
                    payment_method=pay["payment_method"], payment_status=pay["status"], transaction_ref=pay["transaction_ref"], paid_at=pay["paid_at"],
                    shipping_address=o.get("shipping_address"))
    monkeypatch.setattr(orders, "list_orders", lambda uid: sorted([summary_row(o) for o in S.orders.values() if o["user_id"] == uid], key=lambda r: r["order_date"], reverse=True))

    def get_order(uid, oid):
        o = S.orders.get(oid)
        if not o or o["user_id"] != uid: return None
        row = summary_row(o)
        row["items"] = [dict(i, product_name=S.products[i["product_id"]]["product_name"], brand=S.products[i["product_id"]]["brand"],
                             image_url=S.products[i["product_id"]]["image_url"], current_price=S.products[i["product_id"]]["price"],
                             eco_score=S.sust.get(i["product_id"], {}).get("eco_score")) for i in S.order_items if i["order_id"] == oid]
        row["cancellable"] = o["status"] in ("PLACED", "CONFIRMED")
        return row
    monkeypatch.setattr(orders, "get_order", get_order)

    def cancel_order(uid, oid):
        o = S.orders.get(oid)
        if not o or o["user_id"] != uid: raise DBError("You are not allowed to modify this order.")
        if o["status"] not in ("PLACED", "CONFIRMED"): raise DBError(f"Order can no longer be cancelled (status {o['status']}).")
        for i in S.order_items:
            if i["order_id"] == oid: S.products[i["product_id"]]["stock_quantity"] += i["quantity"]
        o["status"] = "CANCELLED"
        S.payments[oid]["status"] = "REFUNDED" if S.payments[oid]["status"] == "PAID" else "FAILED"
    monkeypatch.setattr(orders, "cancel_order", cancel_order)
    monkeypatch.setattr(orders, "has_purchased", lambda uid, pid: any(i["product_id"] == pid and S.orders[i["order_id"]]["user_id"] == uid and S.orders[i["order_id"]]["status"] != "CANCELLED" for i in S.order_items))

    # ---------- reviews ----------
    monkeypatch.setattr(reviews, "for_product", lambda pid, limit=20: [dict(r, full_name=S.users[r["user_id"]]["full_name"], city=S.users[r["user_id"]]["city"]) for r in S.reviews if r["product_id"] == pid][:limit])

    def summary(pid):
        rv = [r for r in S.reviews if r["product_id"] == pid]
        return dict(review_count=len(rv), avg_rating=round(sum(r["rating"] for r in rv) / len(rv), 2) if rv else None,
                    **{f"r{n}": sum(1 for r in rv if r["rating"] == n) for n in range(1, 6)})
    monkeypatch.setattr(reviews, "summary", summary)
    monkeypatch.setattr(reviews, "user_review", lambda uid, pid: next((r for r in S.reviews if r["user_id"] == uid and r["product_id"] == pid), None))

    def submit(uid, pid, rating, title, text):
        try: rating = int(rating)
        except (TypeError, ValueError): raise DBError("Please choose a star rating.")
        if not 1 <= rating <= 5: raise DBError("Rating must be between 1 and 5.")
        if len((text or "").strip()) < 10: raise DBError("Please write at least 10 characters in your review.")
        if reviews.user_review(uid, pid): raise DBError("You have already reviewed this product.")
        S.reviews.append(dict(review_id=S.next_ids["review"], product_id=pid, user_id=uid, rating=rating, title=title, review_text=text,
                              is_verified=1 if orders.has_purchased(uid, pid) else 0, data_origin="LIVE", created_at=datetime.now()))
        S.next_ids["review"] += 1
    monkeypatch.setattr(reviews, "submit", submit)

    # ---------- analytics ----------
    live = [o for o in S.orders.values() if o["status"] != "CANCELLED"]
    monkeypatch.setattr(analytics, "overview", lambda: dict(
        total_products=len(S.products), total_categories=len(S.categories), scored_products=len(S.sust),
        avg_eco_score=round(sum(s["eco_score"] for s in S.sust.values()) / len(S.sust), 1),
        avg_rating=round(sum(r["rating"] for r in S.reviews) / len(S.reviews), 2), total_reviews=len(S.reviews),
        customers=len(S.users), orders=len(live), revenue=sum(o["total_amount"] for o in live),
        avg_order_value=sum(o["total_amount"] for o in live) / len(live), cancelled_orders=len(S.orders) - len(live),
        units_sold=sum(i["quantity"] for i in S.order_items if S.orders[i["order_id"]]["status"] != "CANCELLED"),
        original_products=0, original_orders=0))
    monkeypatch.setattr(analytics, "eco_distribution", lambda: [dict(band=b, product_count=n) for b, n in [("0-19", 3), ("20-39", 30), ("40-59", 30), ("60-79", 30), ("80-100", 22)]])
    monkeypatch.setattr(analytics, "category_scores", lambda: [dict(category_id=c["category_id"], category_name=c["category_name"], slug=c["slug"], product_count=c["product_count"], scored_products=c["product_count"] - 1, avg_eco_score=c["avg_eco_score"], min_eco_score=20, max_eco_score=90, avg_price=500) for c in categories_with_counts()])
    monkeypatch.setattr(analytics, "top_sustainable", lambda limit=10: catalog.top_sustainable(limit))
    monkeypatch.setattr(analytics, "monthly_sales", lambda months=12: [dict(year_month=f"2026-{m:02d}", order_count=5, revenue=12000, avg_order_value=2400) for m in range(1, 11)])
    monkeypatch.setattr(analytics, "popular_products", lambda limit=8: [dict(product_id=p, product_name=S.products[p]["product_name"], category_name="x", price=S.products[p]["price"], eco_score=None, units_sold=9, revenue=1000, order_count=3) for p in list(S.products)[:limit]])
    monkeypatch.setattr(analytics, "category_sales", lambda: [dict(category_name=c["category_name"], units=10, revenue=5000) for c in S.categories.values()])
    monkeypatch.setattr(analytics, "order_status_breakdown", lambda: [dict(status="DELIVERED", n=70), dict(status="CANCELLED", n=6)])
    monkeypatch.setattr(analytics, "missing_sustainability", lambda: [dict(S.products[p], category_name=S.categories[S.products[p]["category_id"]]["category_name"]) for p in S.products if p not in S.sust])
    monkeypatch.setattr(analytics, "sustainable_sales_share", lambda: dict(good_units=100, scored_units=160, all_units=170))
    monkeypatch.setattr(analytics, "top_rated", lambda limit=6: [r for r in S.all_rows() if (r["review_count"] or 0) >= 2][:limit])


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def app(store, monkeypatch):
    install_fake_services(store, monkeypatch)
    app = create_app(TestConfig)
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="demo@example.com", password="Demo@1234"):
    client.get("/login")                                  # establishes the CSRF token in the session
    with client.session_transaction() as sess:
        token = sess.get("_csrf")
    return client.post("/login", data={"email": email, "password": password, "_csrf": token}, follow_redirects=False)


def csrf(client):
    client.get("/")
    with client.session_transaction() as sess:
        return sess.get("_csrf")
