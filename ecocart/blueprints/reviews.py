"""Review submission."""
from flask import Blueprint, flash, g, redirect, request, url_for

from ..db import friendly_error
from ..security import login_required
from ..services import reviews

bp = Blueprint("reviews", __name__)


@bp.post("/product/<int:product_id>/review")
@login_required
def submit(product_id):
    try:
        reviews.submit(g.user_id, product_id, request.form.get("rating"), request.form.get("title"),
                       request.form.get("review_text"))
        flash("Thanks! Your review has been published.", "success")
    except Exception as e:  # noqa: BLE001
        flash(friendly_error(e), "error")
    return redirect(url_for("shop.product", product_id=product_id) + "#reviews")
