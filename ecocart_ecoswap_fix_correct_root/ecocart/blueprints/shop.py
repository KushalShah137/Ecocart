"""Catalogue listing, product details and the Eco Swap JSON API."""
from flask import Blueprint, abort, current_app, g, jsonify, render_template, request

from ..services import catalog, ecoswap, orders, reviews

bp = Blueprint("shop", __name__)


def _num(name, cast=float, lo=None, hi=None):
    raw = request.args.get(name, "").strip()
    if raw == "":
        return None
    try:
        v = cast(raw)
    except ValueError:
        return None
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


@bp.get("/shop")
def shop():
    page = _num("page", int, 1, 10000) or 1
    sort = request.args.get("sort", "featured")
    if sort not in catalog.SORTS:
        sort = "featured"
    filters = dict(
        q=request.args.get("q", "").strip() or None,
        category=request.args.get("category", "").strip() or None,
        min_price=_num("min_price", float, 0, 1e7),
        max_price=_num("max_price", float, 0, 1e7),
        min_eco=_num("min_eco", int, 0, 100),
        max_eco=_num("max_eco", int, 0, 100),
        in_stock=request.args.get("in_stock") == "1",
        has_eco=request.args.get("has_eco") == "1",
    )
    result = catalog.list_products(page=page, page_size=current_app.config["SHOP_PAGE_SIZE"], sort=sort, **filters)
    return render_template("shop.html", result=result, filters=filters, sort=sort, sorts=catalog.SORT_LABELS,
                           categories=catalog.categories_with_counts(), bounds=catalog.price_bounds(),
                           active_category=catalog.get_category(filters["category"]) if filters["category"] else None)


@bp.get("/product/<int:product_id>")
def product(product_id):
    p = catalog.get_product(product_id)
    if not p:
        abort(404)
    swaps, tol = ([], current_app.config["ECO_SWAP_PRICE_TOLERANCE"])
    if p["eco_score"] is not None:
        swaps, tol = ecoswap.recommendations(product_id)
    mine = reviews.user_review(g.user_id, product_id) if g.get("user_id") else None
    can_review = bool(g.get("user_id")) and mine is None
    purchased = orders.has_purchased(g.user_id, product_id) if g.get("user_id") else False
    return render_template("product.html", p=p, swaps=swaps, tolerance=tol,
                           reviews=reviews.for_product(product_id), rsum=reviews.summary(product_id),
                           my_review=mine, can_review=can_review, purchased=purchased)


@bp.get("/api/eco-swap/<int:product_id>")
def api_eco_swap(product_id):
    """JSON endpoint used by the product page's tolerance slider."""
    p = catalog.get_product(product_id)
    if not p:
        return jsonify(error="Product not found"), 404
    if p["eco_score"] is None:
        return jsonify(original=_pub(p), alternatives=[], tolerance=None,
                       message="This product has no Eco-Score yet, so Eco Swap cannot compare it.")
    tol = _num("tolerance", float, 0.0, 1.0)
    swaps, tol = ecoswap.recommendations(product_id, tolerance=tol)
    return jsonify(original=_pub(p), tolerance=tol, alternatives=[_pub_alt(a) for a in swaps])


def _pub(p):
    return dict(product_id=p["product_id"], product_name=p["product_name"], price=float(p["price"]),
                eco_score=p["eco_score"], eco_grade=p.get("eco_grade"), image_url=p["image_url"])


def _pub_alt(a):
    return dict(product_id=a["product_id"], product_name=a["product_name"], brand=a["brand"], price=float(a["price"]),
                eco_score=int(a["eco_score"]), eco_grade=a["eco_grade"], score_gain=int(a["score_gain"]),
                price_diff=float(a["price_diff"]), price_diff_pct=float(a["price_diff_pct"]), image_url=a["image_url"],
                material=a["material"], packaging_type=a["packaging_type"], stock_quantity=int(a["stock_quantity"]),
                reasons=a["reasons"], explanation=a["sustainability_explanation"])
