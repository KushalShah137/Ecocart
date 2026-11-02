"""
Eco Swap: rule-based recommendation engine.

Rules (enforced inside Oracle, in ECOCART_PKG.ECO_SWAP):
  1. both products have the same recognized product-function group
  2. alternative has a sustainability record with a HIGHER Eco-Score
  3. price within +/- tolerance of the original (default 20 %, configurable)
  4. alternative is active and in stock
Unknown product types are excluded rather than matched by broad category alone.
Ordered by Eco-Score (desc), then closeness in price.

Nothing here is AI: it is a deterministic SQL rule set, and the UI says so.
"""
import oracledb
from flask import current_app

from ..db import get_db, query


def _rows(cur):
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def recommendations(product_id: int, tolerance=None, max_rows=None):
    cfg = current_app.config
    tol = cfg["ECO_SWAP_PRICE_TOLERANCE"] if tolerance is None else float(tolerance)
    tol = min(max(tol, 0.0), 1.0)
    lim = cfg["ECO_SWAP_MAX_RESULTS"] if max_rows is None else int(max_rows)
    conn = get_db()
    cur = conn.cursor()
    rc = cur.callfunc("ecocart_pkg.eco_swap", oracledb.DB_TYPE_CURSOR, [product_id, tol, lim])
    rows = _rows(rc)
    for r in rows:
        r["reasons"] = _reasons(r, tol)
    return rows, tol


def _reasons(alt, tol):
    reasons = [f"+{int(alt['score_gain'])} Eco-Score points ({int(alt['eco_score'])} vs the original)"]
    diff = float(alt["price_diff"])
    if diff <= 0:
        reasons.append(f"₹{abs(diff):,.0f} cheaper" if diff < 0 else "Same price")
    else:
        reasons.append(f"₹{diff:,.0f} more, within the ±{int(tol * 100)}% price window")
    reasons.append(f"{alt['material']}, {str(alt['packaging_type']).lower()}")
    reasons.append(f"{int(alt['stock_quantity'])} in stock")
    return reasons


def swap_showcase(limit=6):
    """Home / Eco Swap page: the strongest original->alternative pairs in the catalogue.
    Pure SQL version of the same rules (demonstrates the join without the package)."""
    tol = current_app.config["ECO_SWAP_PRICE_TOLERANCE"]
    return query("""
        SELECT * FROM (
          SELECT orig.product_id        AS orig_id,  orig.product_name AS orig_name,  orig.price AS orig_price,
                 orig.eco_score         AS orig_score, orig.image_url  AS orig_image, orig.category_name,
                 alt.product_id         AS alt_id,   alt.product_name  AS alt_name,   alt.price  AS alt_price,
                 alt.eco_score          AS alt_score, alt.image_url    AS alt_image,
                 alt.eco_score - orig.eco_score AS score_gain,
                 alt.price - orig.price         AS price_diff,
                 ROW_NUMBER() OVER (PARTITION BY orig.product_id ORDER BY alt.eco_score DESC, ABS(alt.price - orig.price)) AS rn
          FROM v_product_catalog orig
          JOIN v_product_catalog alt
            ON alt.category_id = orig.category_id
           AND alt.product_id <> orig.product_id
           AND fn_product_swap_group(orig.category_id, orig.product_name) IS NOT NULL
           AND fn_product_swap_group(alt.category_id, alt.product_name) =
               fn_product_swap_group(orig.category_id, orig.product_name)
           AND alt.eco_score > orig.eco_score
           AND alt.price BETWEEN orig.price * (1 - :tol) AND orig.price * (1 + :tol)
           AND alt.stock_quantity > 0 AND alt.is_active = 1
          WHERE orig.is_active = 1 AND orig.eco_score IS NOT NULL
        )
        WHERE rn = 1
        ORDER BY score_gain DESC, orig_price DESC
        FETCH FIRST :lim ROWS ONLY""", tol=tol, lim=limit)
