"""
Live Oracle integration tests. They run ONLY when the ECOCART schema is reachable
with the settings in .env (ECOCART_DB_*). Otherwise every test is skipped with a
clear reason, so `pytest` still passes on a machine without Oracle.

    pytest tests/test_oracle_integration.py -v

They exercise the real PL/SQL package: checkout, stock reduction, payment
failure rollback, cancellation/stock restore, Eco Swap, views and seed counts.
Every test rolls back its own changes (no commits), so the demo data is untouched.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

oracledb = pytest.importorskip("oracledb")
from ecocart.db import get_connection  # noqa: E402


def _connect_or_skip():
    try:
        return get_connection()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Oracle not reachable ({str(e).splitlines()[0]}); live integration tests skipped")


@pytest.fixture
def conn():
    c = _connect_or_skip()
    yield c
    c.rollback()
    c.close()


def scalar(conn, sql, **b):
    cur = conn.cursor(); cur.execute(sql, b); return cur.fetchone()[0]


def test_connection_and_objects(conn):
    assert scalar(conn, "SELECT 1 FROM dual") == 1
    tables = {r[0] for r in conn.cursor().execute("SELECT table_name FROM user_tables")}
    for t in ("APP_USER", "CATEGORY", "PRODUCT", "PRODUCT_SUSTAINABILITY", "CART", "CART_ITEM", "CUSTOMER_ORDER",
              "ORDER_ITEM", "PAYMENT", "REVIEW"):
        assert t in tables
    invalid = conn.cursor().execute("SELECT object_name FROM user_objects WHERE status = 'INVALID'").fetchall()
    assert invalid == [], f"invalid objects: {invalid}"


def test_seed_counts_meet_targets(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM category") >= 8
    assert 100 <= scalar(conn, "SELECT COUNT(*) FROM product")
    assert scalar(conn, "SELECT COUNT(*) FROM app_user") >= 30
    assert scalar(conn, "SELECT COUNT(*) FROM customer_order") >= 60
    assert scalar(conn, "SELECT COUNT(*) FROM order_item") >= 100
    assert scalar(conn, "SELECT COUNT(*) FROM review") >= 50
    assert scalar(conn, "SELECT COUNT(*) FROM v_missing_sustainability") > 0


def test_seed_is_idempotent(conn):
    """Re-running the seed must not change row counts (IGNORE_ROW_ON_DUPKEY_INDEX)."""
    before = scalar(conn, "SELECT COUNT(*) FROM product")
    cur = conn.cursor()
    cur.execute("""INSERT /*+ IGNORE_ROW_ON_DUPKEY_INDEX(product, pk_product) */ INTO product
                   (product_id, category_id, product_name, price, stock_quantity)
                   SELECT product_id, category_id, product_name, price, stock_quantity FROM product WHERE ROWNUM <= 5""")
    assert scalar(conn, "SELECT COUNT(*) FROM product") == before


def test_order_totals_match_items(conn):
    assert scalar(conn, """SELECT COUNT(*) FROM customer_order o
                           WHERE o.subtotal <> (SELECT SUM(line_total) FROM order_item oi WHERE oi.order_id = o.order_id)""") == 0
    assert scalar(conn, "SELECT COUNT(*) FROM customer_order o JOIN payment p ON p.order_id = o.order_id WHERE p.amount <> o.total_amount") == 0


def _demo_user(conn):
    return scalar(conn, "SELECT user_id FROM app_user WHERE email = 'demo@example.com'")


def _fresh_cart(conn, user_id, product_id, qty):
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_item WHERE cart_id IN (SELECT cart_id FROM cart WHERE user_id = :u AND status = 'ACTIVE')", u=user_id)
    cur.execute("DELETE FROM cart WHERE user_id = :u AND status = 'ACTIVE'", u=user_id)
    out = cur.var(int)
    cur.execute("INSERT INTO cart (user_id, status) VALUES (:u, 'ACTIVE') RETURNING cart_id INTO :o", u=user_id, o=out)
    cart_id = out.getvalue()[0]
    cur.execute("INSERT INTO cart_item (cart_id, product_id, quantity) VALUES (:c, :p, :q)", c=cart_id, p=product_id, q=qty)
    return cart_id


def test_place_order_reduces_stock_and_creates_payment(conn):
    uid = _demo_user(conn)
    pid, stock = conn.cursor().execute("SELECT product_id, stock_quantity FROM product WHERE stock_quantity > 10 AND is_active = 1 FETCH FIRST 1 ROWS ONLY").fetchone()
    _fresh_cart(conn, uid, pid, 2)
    cur = conn.cursor()
    oid, ref = cur.var(int), cur.var(str)
    cur.callproc("ecocart_pkg.place_order", [uid, "DEMO_UPI", "12, MG Road, Vellore, Tamil Nadu - 632001", 0, oid, ref])
    order_id = oid.getvalue()
    assert ref.getvalue().startswith("EC-")
    assert scalar(conn, "SELECT stock_quantity FROM product WHERE product_id = :p", p=pid) == stock - 2
    assert scalar(conn, "SELECT status FROM payment WHERE order_id = :o", o=order_id) == "PAID"
    assert scalar(conn, "SELECT status FROM customer_order WHERE order_id = :o", o=order_id) == "CONFIRMED"
    assert scalar(conn, "SELECT COUNT(*) FROM cart WHERE user_id = :u AND status = 'ACTIVE'", u=uid) == 0
    # cancellation restores stock and refunds
    conn.cursor().callproc("ecocart_pkg.cancel_order", [order_id, uid])
    assert scalar(conn, "SELECT stock_quantity FROM product WHERE product_id = :p", p=pid) == stock
    assert scalar(conn, "SELECT status FROM payment WHERE order_id = :o", o=order_id) == "REFUNDED"


def test_payment_failure_rolls_back_everything(conn):
    uid = _demo_user(conn)
    pid, stock = conn.cursor().execute("SELECT product_id, stock_quantity FROM product WHERE stock_quantity > 10 AND is_active = 1 FETCH FIRST 1 ROWS ONLY").fetchone()
    _fresh_cart(conn, uid, pid, 1)
    orders_before = scalar(conn, "SELECT COUNT(*) FROM customer_order")
    cur = conn.cursor()
    with pytest.raises(oracledb.DatabaseError) as exc:
        cur.callproc("ecocart_pkg.place_order", [uid, "DEMO_CARD", "12, MG Road, Vellore, Tamil Nadu - 632001", 1, cur.var(int), cur.var(str)])
    assert "ORA-20030" in str(exc.value)
    assert scalar(conn, "SELECT COUNT(*) FROM customer_order") == orders_before
    assert scalar(conn, "SELECT stock_quantity FROM product WHERE product_id = :p", p=pid) == stock
    assert scalar(conn, "SELECT status FROM cart WHERE user_id = :u AND status = 'ACTIVE'", u=uid) == "ACTIVE"


def test_overselling_is_prevented(conn):
    uid = _demo_user(conn)
    pid, stock = conn.cursor().execute("SELECT product_id, stock_quantity FROM product WHERE stock_quantity BETWEEN 1 AND 40 FETCH FIRST 1 ROWS ONLY").fetchone()
    _fresh_cart(conn, uid, pid, int(stock) + 1)
    cur = conn.cursor()
    with pytest.raises(oracledb.DatabaseError) as exc:
        cur.callproc("ecocart_pkg.place_order", [uid, "COD", "12, MG Road, Vellore, Tamil Nadu - 632001", 0, cur.var(int), cur.var(str)])
    assert "ORA-20011" in str(exc.value)


def test_cancel_requires_ownership(conn):
    other_order, owner = conn.cursor().execute("SELECT order_id, user_id FROM customer_order WHERE status IN ('PLACED','CONFIRMED') FETCH FIRST 1 ROWS ONLY").fetchone()
    stranger = scalar(conn, "SELECT MIN(user_id) FROM app_user WHERE user_id <> :o", o=owner)
    with pytest.raises(oracledb.DatabaseError) as exc:
        conn.cursor().callproc("ecocart_pkg.cancel_order", [other_order, stranger])
    assert "ORA-20040" in str(exc.value)


def test_eco_swap_rules(conn):
    pid = scalar(conn, "SELECT product_id FROM product WHERE product_name = 'Polyester Laptop Backpack 25L'")
    cur = conn.cursor()
    rc = cur.callfunc("ecocart_pkg.eco_swap", oracledb.DB_TYPE_CURSOR, [pid, 0.20, 4])
    cols = [d[0].lower() for d in rc.description]
    rows = [dict(zip(cols, r)) for r in rc.fetchall()]
    assert rows and rows[0]["product_name"] == "Recycled-Fabric Laptop Backpack 25L"
    orig_price, orig_score = conn.cursor().execute("SELECT price, eco_score FROM v_product_catalog WHERE product_id = :p", p=pid).fetchone()
    for r in rows:
        assert r["eco_score"] > orig_score and r["stock_quantity"] > 0
        assert float(orig_price) * 0.8 <= float(r["price"]) <= float(orig_price) * 1.2
    assert [r["eco_score"] for r in rows] == sorted([r["eco_score"] for r in rows], reverse=True)


def test_views_and_constraints(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM v_product_catalog") == scalar(conn, "SELECT COUNT(*) FROM product")
    assert scalar(conn, "SELECT fn_eco_grade(80) FROM dual") == "A"
    assert scalar(conn, "SELECT fn_compute_eco_score(85, 90, 45, 85) FROM dual") == 78
    with pytest.raises(oracledb.DatabaseError):           # CHECK (rating BETWEEN 1 AND 5)
        conn.cursor().execute("INSERT INTO review (product_id, user_id, rating, review_text) VALUES (1, 1, 7, 'x')")
    with pytest.raises(oracledb.DatabaseError):           # FK: product must exist
        conn.cursor().execute("INSERT INTO product_sustainability (product_id, material, packaging_type, eco_score) VALUES (999999, 'x', 'y', 50)")
