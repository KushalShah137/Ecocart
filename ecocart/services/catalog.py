"""Product catalogue queries (all read from V_PRODUCT_CATALOG)."""
from ..db import query, query_one

# Whitelisted sort keys -> ORDER BY fragments. User input is only ever a key of this dict.
SORTS = {
    "featured":   "is_featured DESC, eco_score DESC NULLS LAST, product_id",
    "price_asc":  "price ASC, product_id",
    "price_desc": "price DESC, product_id",
    "rating":     "avg_rating DESC NULLS LAST, review_count DESC, product_id",
    "eco_desc":   "eco_score DESC NULLS LAST, product_id",
    "eco_asc":    "eco_score ASC NULLS LAST, product_id",
    "newest":     "created_at DESC, product_id",
    "name":       "product_name ASC",
}
SORT_LABELS = {
    "featured": "Featured", "price_asc": "Price: low to high", "price_desc": "Price: high to low",
    "rating": "Customer rating", "eco_desc": "Eco-Score: high to low", "eco_asc": "Eco-Score: low to high",
    "newest": "Newest", "name": "Name A-Z",
}

BASE = "SELECT * FROM v_product_catalog WHERE is_active = 1"


def _filters(q=None, category=None, min_price=None, max_price=None, min_eco=None, max_eco=None, in_stock=False,
             has_eco=False):
    where, binds = [], {}
    if q:
        where.append("UPPER(product_name) LIKE '%' || UPPER(:q) || '%'")
        binds["q"] = q.strip()[:100]
    if category:
        where.append("category_slug = :cat")
        binds["cat"] = category
    if min_price is not None:
        where.append("price >= :minp"); binds["minp"] = float(min_price)
    if max_price is not None:
        where.append("price <= :maxp"); binds["maxp"] = float(max_price)
    if min_eco is not None:
        where.append("eco_score >= :mine"); binds["mine"] = int(min_eco)
    if max_eco is not None:
        where.append("eco_score <= :maxe"); binds["maxe"] = int(max_eco)
    if in_stock:
        where.append("stock_quantity > 0")
    if has_eco:
        where.append("eco_score IS NOT NULL")
    return (" AND " + " AND ".join(where) if where else ""), binds


def list_products(page=1, page_size=12, sort="featured", **filters):
    sort_sql = SORTS.get(sort, SORTS["featured"])
    where_sql, binds = _filters(**filters)
    total = query_one(f"SELECT COUNT(*) AS n FROM v_product_catalog WHERE is_active = 1{where_sql}", **binds)["n"]
    page = max(1, int(page))
    offset = (page - 1) * page_size
    rows = query(f"{BASE}{where_sql} ORDER BY {sort_sql} OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY",
                 off=offset, lim=page_size, **binds)
    pages = max(1, (total + page_size - 1) // page_size)
    return dict(items=rows, total=total, page=page, pages=pages, page_size=page_size)


def get_product(product_id: int):
    return query_one(f"{BASE} AND product_id = :pid", pid=product_id)


def featured_products(limit=8):
    return query(f"{BASE} AND is_featured = 1 ORDER BY eco_score DESC NULLS LAST FETCH FIRST :lim ROWS ONLY", lim=limit)


def top_sustainable(limit=8):
    return query(f"{BASE} AND eco_score IS NOT NULL AND stock_quantity > 0 "
                 "ORDER BY eco_score DESC, avg_rating DESC NULLS LAST FETCH FIRST :lim ROWS ONLY", lim=limit)


def categories_with_counts():
    return query("""
        SELECT c.category_id, c.category_name, c.slug, c.description, c.icon,
               COUNT(p.product_id) AS product_count,
               ROUND(AVG(ps.eco_score), 0) AS avg_eco_score,
               MIN(p.price) AS min_price
        FROM category c
        LEFT JOIN product p ON p.category_id = c.category_id AND p.is_active = 1
        LEFT JOIN product_sustainability ps ON ps.product_id = p.product_id
        GROUP BY c.category_id, c.category_name, c.slug, c.description, c.icon
        ORDER BY c.category_name""")


def get_category(slug):
    return query_one("SELECT * FROM category WHERE slug = :s", s=slug)


def price_bounds():
    return query_one("SELECT MIN(price) AS min_price, MAX(price) AS max_price FROM product WHERE is_active = 1")


def home_stats():
    return query_one("""
        SELECT (SELECT COUNT(*) FROM product WHERE is_active = 1)                                   AS products,
               (SELECT COUNT(*) FROM category)                                                       AS categories,
               (SELECT COUNT(*) FROM product_sustainability ps JOIN product p ON p.product_id = ps.product_id WHERE p.is_active = 1) AS scored,
               (SELECT ROUND(AVG(eco_score), 1) FROM product_sustainability)                         AS avg_eco,
               (SELECT COUNT(*) FROM product_sustainability WHERE eco_score >= 65)                   AS good_or_better,
               (SELECT COUNT(*) FROM customer_order WHERE status <> 'CANCELLED')                     AS orders
        FROM dual""")
