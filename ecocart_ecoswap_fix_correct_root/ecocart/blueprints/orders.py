"""Order history, order detail / confirmation and cancellation."""
from flask import Blueprint, abort, flash, g, redirect, render_template, url_for

from ..db import friendly_error
from ..security import login_required
from ..services import orders

bp = Blueprint("orders", __name__, url_prefix="/orders")


@bp.get("")
@login_required
def history():
    return render_template("orders/list.html", orders=orders.list_orders(g.user_id))


@bp.get("/<int:order_id>")
@login_required
def detail(order_id):
    order = orders.get_order(g.user_id, order_id)   # returns None for other users' orders -> 404, never leaks
    if not order:
        abort(404)
    return render_template("orders/detail.html", order=order, confirmation=False)


@bp.get("/<int:order_id>/confirmation")
@login_required
def confirmation(order_id):
    order = orders.get_order(g.user_id, order_id)
    if not order:
        abort(404)
    return render_template("orders/detail.html", order=order, confirmation=True)


@bp.post("/<int:order_id>/cancel")
@login_required
def cancel(order_id):
    try:
        orders.cancel_order(g.user_id, order_id)
        flash("Order cancelled and stock restored.", "success")
    except Exception as e:  # noqa: BLE001
        flash(friendly_error(e), "error")
    return redirect(url_for("orders.detail", order_id=order_id))
