"""Home, categories and the Eco Swap / methodology pages."""
from flask import Blueprint, render_template

from ..eco_methodology import GRADE_BANDS, WEIGHTS
from ..services import analytics, catalog, ecoswap

bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    return render_template(
        "index.html",
        featured=catalog.featured_products(8),
        sustainable=catalog.top_sustainable(4),
        categories=catalog.categories_with_counts(),
        stats=catalog.home_stats(),
        swaps=ecoswap.swap_showcase(3),
    )


@bp.get("/categories")
def categories():
    return render_template("categories.html", categories=catalog.categories_with_counts())


@bp.get("/eco-swap")
def eco_swap_page():
    return render_template("ecoswap.html", swaps=ecoswap.swap_showcase(9))


@bp.get("/sustainability")
def sustainability():
    return render_template("sustainability.html", weights=WEIGHTS, bands=GRADE_BANDS,
                           missing=analytics.missing_sustainability(), overview=analytics.overview())
