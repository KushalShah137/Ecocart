"""Cart pages and checkout."""
from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from ..db import friendly_error
from ..security import login_required
from ..services import cart as cart_service
from ..services import orders, users

bp = Blueprint("cart", __name__)


def _wants_json():
    return request.is_json or request.headers.get("X-Requested-With") == "fetch"


@bp.get("/cart")
@login_required
def view():
    return render_template("cart.html", cart=cart_service.get_cart(g.user_id))


@bp.post("/cart/add")
@login_required
def add():
    data = request.get_json(silent=True) or request.form
    try:
        name = cart_service.add_item(g.user_id, int(data.get("product_id", 0)), data.get("quantity", 1))
        msg = f"Added {name} to your cart."
        if _wants_json():
            return jsonify(ok=True, message=msg, count=cart_service.item_count(g.user_id))
        flash(msg, "success")
    except Exception as e:  # noqa: BLE001
        msg = friendly_error(e)
        if _wants_json():
            return jsonify(ok=False, message=msg), 400
        flash(msg, "error")
    return redirect(request.form.get("next") or url_for("cart.view"))


@bp.post("/cart/update")
@login_required
def update():
    data = request.get_json(silent=True) or request.form
    try:
        cart_service.update_item(g.user_id, int(data.get("product_id", 0)), data.get("quantity"))
        if _wants_json():
            return jsonify(ok=True, cart=_cart_json())
        flash("Cart updated.", "success")
    except Exception as e:  # noqa: BLE001
        msg = friendly_error(e)
        if _wants_json():
            return jsonify(ok=False, message=msg, cart=_cart_json()), 400
        flash(msg, "error")
    return redirect(url_for("cart.view"))


@bp.post("/cart/remove")
@login_required
def remove():
    data = request.get_json(silent=True) or request.form
    cart_service.remove_item(g.user_id, int(data.get("product_id", 0)))
    if _wants_json():
        return jsonify(ok=True, cart=_cart_json())
    flash("Item removed.", "info")
    return redirect(url_for("cart.view"))


def _cart_json():
    c = cart_service.get_cart(g.user_id)
    return dict(count=c["count"], subtotal=c["subtotal"], shipping=c["shipping"], total=c["total"],
                items=[dict(product_id=i["product_id"], quantity=int(i["quantity"]), line_total=float(i["line_total"]))
                       for i in c["items"]])


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = cart_service.get_cart(g.user_id)
    user = users.get_by_id(g.user_id)
    if not cart["items"]:
        flash("Your cart is empty.", "info")
        return redirect(url_for("shop.shop"))
    default_address = ", ".join(x for x in (user["address_line"], user["city"], user["state"], user["pincode"]) if x)
    if request.method == "POST":
        method = request.form.get("payment_method", "")
        address = request.form.get("shipping_address", "")
        simulate_failure = request.form.get("simulate_failure") == "1"
        try:
            order_id, ref = orders.place_order(g.user_id, method, address, simulate_failure)
        except Exception as e:  # noqa: BLE001
            flash(friendly_error(e), "error")
            return render_template("checkout.html", cart=cart_service.get_cart(g.user_id), methods=orders.PAYMENT_METHODS,
                                   address=address or default_address, chosen=method), 400
        flash(f"Order {ref} placed successfully.", "success")
        return redirect(url_for("orders.confirmation", order_id=order_id))
    return render_template("checkout.html", cart=cart, methods=orders.PAYMENT_METHODS, address=default_address, chosen="COD")
