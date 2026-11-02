"""Checkout, order history and cancellation. Checkout runs inside ECOCART_PKG.PLACE_ORDER."""
import oracledb

from ..db import DBError, get_db, query, query_one, transaction

PAYMENT_METHODS = [
    ("COD", "Cash on Delivery", "Pay in cash when your order arrives."),
    ("DEMO_UPI", "Demo UPI", "Simulated UPI payment - no real money moves."),
    ("DEMO_CARD", "Demo Card", "Simulated card payment - no card details are collected."),
    ("DEMO_WALLET", "Demo Wallet", "Simulated wallet payment."),
]
METHOD_KEYS = {m[0] for m in PAYMENT_METHODS}


def place_order(user_id, payment_method, shipping_address, simulate_failure=False):
    """Returns (order_id, order_ref). Raises DBError with a user-safe message; nothing is persisted on failure."""
    if payment_method not in METHOD_KEYS:
        raise DBError("Please choose a valid payment method.")
    shipping_address = (shipping_address or "").strip()
    if len(shipping_address) < 10:
        raise DBError("Please enter a complete shipping address.")
    with transaction() as conn:
        cur = conn.cursor()
        out_id = cur.var(int)
        out_ref = cur.var(str)
        cur.callproc("ecocart_pkg.place_order",
                     [user_id, payment_method, shipping_address[:400], 1 if simulate_failure else 0, out_id, out_ref])
        return int(out_id.getvalue()), out_ref.getvalue()


def cancel_order(user_id, order_id):
    with transaction() as conn:
        conn.cursor().callproc("ecocart_pkg.cancel_order", [order_id, user_id])


def list_orders(user_id):
    # Authorisation: the WHERE clause on user_id is the only way rows are selected.
    return query("SELECT * FROM v_order_summary WHERE user_id = :u ORDER BY order_date DESC", u=user_id)


def get_order(user_id, order_id):
    order = query_one("SELECT * FROM v_order_summary WHERE order_id = :o AND user_id = :u", o=order_id, u=user_id)
    if not order:
        return None
    order["items"] = query("""
        SELECT oi.product_id, oi.quantity, oi.unit_price, oi.line_total, p.product_name, p.brand, p.image_url,
               p.price AS current_price, ps.eco_score
        FROM order_item oi
        JOIN product p ON p.product_id = oi.product_id
        LEFT JOIN product_sustainability ps ON ps.product_id = p.product_id
        WHERE oi.order_id = :o ORDER BY oi.order_item_id""", o=order_id)
    order["cancellable"] = order["order_status"] in ("PLACED", "CONFIRMED")
    return order


def has_purchased(user_id, product_id):
    row = query_one("""SELECT 1 AS x FROM customer_order o JOIN order_item oi ON oi.order_id = o.order_id
                       WHERE o.user_id = :u AND oi.product_id = :p AND o.status <> 'CANCELLED' FETCH FIRST 1 ROWS ONLY""",
                    u=user_id, p=product_id)
    return row is not None
