"""Shopping cart persisted in CART / CART_ITEM. Prices always come from PRODUCT."""
from ..db import DBError, execute, get_db, query, query_one, transaction

MAX_QTY = 50


def _active_cart_id(user_id, create=False):
    row = query_one("SELECT cart_id FROM cart WHERE user_id = :u AND status = 'ACTIVE'", u=user_id)
    if row:
        return row["cart_id"]
    if not create:
        return None
    cur = get_db().cursor()
    out = cur.var(int)
    cur.execute("INSERT INTO cart (user_id, status) VALUES (:u, 'ACTIVE') RETURNING cart_id INTO :o", u=user_id, o=out)
    return out.getvalue()[0]


def get_cart(user_id):
    cart_id = _active_cart_id(user_id)
    items = [] if cart_id is None else query("""
        SELECT ci.cart_item_id, ci.product_id, ci.quantity, p.product_name, p.brand, p.price, p.image_url,
               p.stock_quantity, p.is_active, ps.eco_score,
               ROUND(p.price * ci.quantity, 2) AS line_total
        FROM cart_item ci
        JOIN product p ON p.product_id = ci.product_id
        LEFT JOIN product_sustainability ps ON ps.product_id = p.product_id
        WHERE ci.cart_id = :c
        ORDER BY ci.added_at, ci.cart_item_id""", c=cart_id)
    subtotal = sum(float(i["line_total"]) for i in items)
    shipping = 0.0 if subtotal >= 999 or not items else 49.0
    problems = [i for i in items if i["stock_quantity"] < i["quantity"] or i["is_active"] != 1]
    return dict(cart_id=cart_id, items=items, count=sum(int(i["quantity"]) for i in items), subtotal=subtotal,
                shipping=shipping, total=subtotal + shipping, problems=problems)


def item_count(user_id):
    row = query_one("""SELECT NVL(SUM(ci.quantity), 0) AS n FROM cart c JOIN cart_item ci ON ci.cart_id = c.cart_id
                       WHERE c.user_id = :u AND c.status = 'ACTIVE'""", u=user_id)
    return int(row["n"]) if row else 0


def _check_qty(qty):
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        raise DBError("Quantity must be a whole number.")
    if qty < 1 or qty > MAX_QTY:
        raise DBError(f"Quantity must be between 1 and {MAX_QTY}.")
    return qty


def add_item(user_id, product_id, qty=1):
    qty = _check_qty(qty)
    with transaction():
        p = query_one("SELECT product_id, product_name, stock_quantity, is_active FROM product WHERE product_id = :p", p=product_id)
        if not p or p["is_active"] != 1:
            raise DBError("That product is not available.")
        cart_id = _active_cart_id(user_id, create=True)
        existing = query_one("SELECT quantity FROM cart_item WHERE cart_id = :c AND product_id = :p", c=cart_id, p=product_id)
        new_qty = qty + (int(existing["quantity"]) if existing else 0)
        if new_qty > p["stock_quantity"]:
            raise DBError(f"Only {int(p['stock_quantity'])} unit(s) of {p['product_name']} are in stock.")
        if new_qty > MAX_QTY:
            raise DBError(f"You can order at most {MAX_QTY} units of one product.")
        if existing:
            execute("UPDATE cart_item SET quantity = :q WHERE cart_id = :c AND product_id = :p", q=new_qty, c=cart_id, p=product_id)
        else:
            execute("INSERT INTO cart_item (cart_id, product_id, quantity) VALUES (:c, :p, :q)", c=cart_id, p=product_id, q=new_qty)
    return p["product_name"]


def update_item(user_id, product_id, qty):
    qty = _check_qty(qty)
    with transaction():
        cart_id = _active_cart_id(user_id)
        if cart_id is None:
            raise DBError("Your cart is empty.")
        p = query_one("SELECT stock_quantity, product_name FROM product WHERE product_id = :p AND is_active = 1", p=product_id)
        if not p:
            raise DBError("That product is not available.")
        if qty > p["stock_quantity"]:
            raise DBError(f"Only {int(p['stock_quantity'])} unit(s) of {p['product_name']} are in stock.")
        n = execute("UPDATE cart_item SET quantity = :q WHERE cart_id = :c AND product_id = :p", q=qty, c=cart_id, p=product_id)
        if n == 0:
            raise DBError("That item is not in your cart.")


def remove_item(user_id, product_id):
    with transaction():
        cart_id = _active_cart_id(user_id)
        if cart_id is not None:
            execute("DELETE FROM cart_item WHERE cart_id = :c AND product_id = :p", c=cart_id, p=product_id)
            execute("UPDATE cart SET updated_at = SYSTIMESTAMP WHERE cart_id = :c", c=cart_id)


def clear(user_id):
    with transaction():
        cart_id = _active_cart_id(user_id)
        if cart_id is not None:
            execute("DELETE FROM cart_item WHERE cart_id = :c", c=cart_id)
            execute("UPDATE cart SET updated_at = SYSTIMESTAMP WHERE cart_id = :c", c=cart_id)
