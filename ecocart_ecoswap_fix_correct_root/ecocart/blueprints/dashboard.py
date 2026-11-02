"""Sustainability dashboard (HTML) and its JSON feed for Chart.js."""
from flask import Blueprint, jsonify, render_template

from ..services import analytics

bp = Blueprint("dashboard", __name__)


def _f(v):
    return float(v) if v is not None else None


@bp.get("/dashboard")
def dashboard():
    share = analytics.sustainable_sales_share()
    share_pct = None
    if share and share["scored_units"]:
        share_pct = round(100.0 * float(share["good_units"]) / float(share["scored_units"]), 1)
    return render_template("dashboard.html", overview=analytics.overview(), top=analytics.top_sustainable(8),
                           popular=analytics.popular_products(8), categories=analytics.category_scores(),
                           statuses=analytics.order_status_breakdown(), top_rated=analytics.top_rated(6),
                           share=share, share_pct=share_pct)


@bp.get("/api/dashboard")
def api_dashboard():
    return jsonify(
        eco_distribution=[dict(band=r["band"], count=int(r["product_count"])) for r in analytics.eco_distribution()],
        category_scores=[dict(category=r["category_name"], avg_eco=_f(r["avg_eco_score"]), products=int(r["product_count"]),
                              scored=int(r["scored_products"])) for r in analytics.category_scores()],
        monthly_sales=[dict(month=r["year_month"], orders=int(r["order_count"]), revenue=_f(r["revenue"]),
                            aov=_f(r["avg_order_value"])) for r in analytics.monthly_sales(12)],
        category_sales=[dict(category=r["category_name"], units=int(r["units"]), revenue=_f(r["revenue"]))
                        for r in analytics.category_sales()],
        popular=[dict(name=r["product_name"], units=int(r["units_sold"]), revenue=_f(r["revenue"]))
                 for r in analytics.popular_products(8)],
        statuses=[dict(status=r["status"], count=int(r["n"])) for r in analytics.order_status_breakdown()],
    )
