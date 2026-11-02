"""EcoCart Flask application factory."""
import logging
import os
import sys
from datetime import datetime

from flask import Flask, g, render_template, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config  # noqa: E402

from . import db as database  # noqa: E402
from .eco_methodology import METHODOLOGY_VERSION, WEIGHTS, eco_grade, grade_label  # noqa: E402
from .security import csrf_protect, csrf_token, load_current_user  # noqa: E402


def create_app(config_object=Config):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    database.init_app(app)

    from .blueprints import auth, cart, dashboard, main, orders, reviews, shop  # noqa: WPS433
    for bp in (main.bp, shop.bp, auth.bp, cart.bp, orders.bp, reviews.bp, dashboard.bp):
        app.register_blueprint(bp)

    app.before_request(load_current_user)
    app.before_request(csrf_protect)

    # ---- template helpers -------------------------------------------------------
    @app.template_filter("inr")
    def inr(value):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "₹0"
        return "₹{:,.0f}".format(v) if v == int(v) else "₹{:,.2f}".format(v)

    @app.template_filter("grade")
    def grade_filter(score):
        return eco_grade(score)

    @app.template_filter("gradelabel")
    def grade_label_filter(score):
        return grade_label(eco_grade(score))

    @app.template_filter("dt")
    def dt_filter(value, fmt="%d %b %Y"):
        if not value:
            return ""
        if isinstance(value, str):
            return value
        return value.strftime(fmt)

    @app.template_filter("stars")
    def stars(value):
        try:
            v = round(float(value or 0))
        except (TypeError, ValueError):
            v = 0
        return "★" * v + "☆" * (5 - v)

    @app.context_processor
    def inject_globals():
        cart_count = 0
        if g.get("user_id"):
            try:
                from .services import cart as cart_service
                cart_count = cart_service.item_count(g.user_id)
            except Exception:  # noqa: BLE001 - never let the nav bar break a page
                cart_count = 0
        return dict(csrf_token=csrf_token, cart_count=cart_count, now=datetime.now(),
                    methodology=METHODOLOGY_VERSION, weights=WEIGHTS, current_path=request.path)

    # ---- error pages --------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("errors/400.html", message=getattr(e, "description", "")), 400

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("errors/500.html"), 500

    @app.errorhandler(database.oracledb.Error)
    def db_error(e):
        app.logger.exception("Database error: %s", e)
        return render_template("errors/500.html", db_down=True), 500

    @app.get("/health")
    def health():
        try:
            database.query_one("SELECT 1 AS ok FROM dual")
            return {"status": "ok", "database": "connected"}
        except Exception as e:  # noqa: BLE001
            return {"status": "degraded", "database": str(e).splitlines()[0]}, 503

    return app
