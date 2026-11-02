"""Sustainability dashboard analytics. Every number is an Oracle aggregation; nothing is hard-coded."""
from ..db import query, query_one


def overview():
    return query_one("""
        SELECT
          (SELECT COUNT(*) FROM product WHERE is_active = 1)                                         AS total_products,
          (SELECT COUNT(*) FROM category)                                                             AS total_categories,
          (SELECT COUNT(*) FROM product_sustainability ps JOIN product p ON p.product_id = ps.product_id
            WHERE p.is_active = 1)                                                                    AS scored_products,
          (SELECT ROUND(AVG(ps.eco_score), 1) FROM product_sustainability ps)                          AS avg_eco_score,
          (SELECT ROUND(AVG(rating), 2) FROM review)                                                  AS avg_rating,
          (SELECT COUNT(*) FROM review)                                                               AS total_reviews,
          (SELECT COUNT(*) FROM app_user WHERE role = 'CUSTOMER')                                     AS customers,
          (SELECT COUNT(*) FROM customer_order WHERE status <> 'CANCELLED')                           AS orders,
          (SELECT NVL(SUM(total_amount), 0) FROM customer_order WHERE status <> 'CANCELLED')          AS revenue,
          (SELECT ROUND(AVG(total_amount), 2) FROM customer_order WHERE status <> 'CANCELLED')        AS avg_order_value,
          (SELECT COUNT(*) FROM customer_order WHERE status = 'CANCELLED')                            AS cancelled_orders,
          (SELECT NVL(SUM(oi.quantity), 0) FROM order_item oi JOIN customer_order o ON o.order_id = oi.order_id
            WHERE o.status <> 'CANCELLED')                                                            AS units_sold,
          (SELECT COUNT(*) FROM product WHERE data_origin = 'ORIGINAL')                               AS original_products,
          (SELECT COUNT(*) FROM customer_order WHERE data_origin = 'ORIGINAL')                        AS original_orders
        FROM dual""")


def eco_distribution():
    return query("SELECT band, product_count FROM v_eco_score_distribution ORDER BY band_order")


def category_scores():
    return query("SELECT * FROM v_category_sustainability ORDER BY avg_eco_score DESC NULLS LAST")


def top_sustainable(limit=10):
    return query("""SELECT product_id, product_name, category_name, price, eco_score, eco_grade, avg_rating, image_url
                    FROM v_product_catalog WHERE eco_score IS NOT NULL AND is_active = 1
                    ORDER BY eco_score DESC, avg_rating DESC NULLS LAST FETCH FIRST :lim ROWS ONLY""", lim=limit)


def monthly_sales(months=12):
    return query("""SELECT year_month, order_count, revenue, avg_order_value FROM v_monthly_sales
                    ORDER BY year_month DESC FETCH FIRST :m ROWS ONLY""", m=months)[::-1]


def popular_products(limit=8):
    return query("SELECT * FROM v_popular_products ORDER BY units_sold DESC, revenue DESC FETCH FIRST :lim ROWS ONLY",
                 lim=limit)


def category_sales():
    return query("""
        SELECT c.category_name, SUM(oi.quantity) AS units, SUM(oi.line_total) AS revenue
        FROM order_item oi
        JOIN customer_order o ON o.order_id = oi.order_id AND o.status <> 'CANCELLED'
        JOIN product p ON p.product_id = oi.product_id
        JOIN category c ON c.category_id = p.category_id
        GROUP BY c.category_name
        ORDER BY revenue DESC""")


def order_status_breakdown():
    return query("SELECT status, COUNT(*) AS n FROM customer_order GROUP BY status ORDER BY n DESC")


def missing_sustainability():
    return query("SELECT * FROM v_missing_sustainability ORDER BY category_name, product_name")


def sustainable_sales_share():
    """Share of non-cancelled units sold that have Eco-Score >= 65 (grade B or better).
    Estimate labelled as such in the UI: it only counts products with a sustainability record."""
    return query_one("""
        SELECT SUM(CASE WHEN ps.eco_score >= 65 THEN oi.quantity ELSE 0 END) AS good_units,
               SUM(CASE WHEN ps.eco_score IS NOT NULL THEN oi.quantity ELSE 0 END) AS scored_units,
               SUM(oi.quantity) AS all_units
        FROM order_item oi
        JOIN customer_order o ON o.order_id = oi.order_id AND o.status <> 'CANCELLED'
        LEFT JOIN product_sustainability ps ON ps.product_id = oi.product_id""")


def top_rated(limit=6):
    return query("""SELECT product_id, product_name, category_name, avg_rating, review_count, eco_score, image_url, price
                    FROM v_product_catalog WHERE review_count >= 2
                    ORDER BY avg_rating DESC, review_count DESC FETCH FIRST :lim ROWS ONLY""", lim=limit)
