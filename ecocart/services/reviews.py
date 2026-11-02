"""Reviews. Policy: one review per customer per product (UQ_REVIEW_USER_PROD);
a review is marked verified when the customer has a non-cancelled order containing the product."""
from ..db import DBError, execute, query, query_one, transaction
from .orders import has_purchased


def for_product(product_id, limit=20):
    return query("""
        SELECT r.review_id, r.rating, r.title, r.review_text, r.is_verified, r.created_at, r.data_origin,
               u.full_name, u.city
        FROM review r JOIN app_user u ON u.user_id = r.user_id
        WHERE r.product_id = :p
        ORDER BY r.created_at DESC
        FETCH FIRST :lim ROWS ONLY""", p=product_id, lim=limit)


def summary(product_id):
    row = query_one("""
        SELECT COUNT(*) AS review_count, ROUND(AVG(rating), 2) AS avg_rating,
               SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS r5,
               SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS r4,
               SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS r3,
               SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS r2,
               SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS r1
        FROM review WHERE product_id = :p""", p=product_id)
    return row


def user_review(user_id, product_id):
    return query_one("SELECT * FROM review WHERE user_id = :u AND product_id = :p", u=user_id, p=product_id)


def submit(user_id, product_id, rating, title, text):
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise DBError("Please choose a star rating.")
    if not 1 <= rating <= 5:
        raise DBError("Rating must be between 1 and 5.")
    title = (title or "").strip()[:120]
    text = (text or "").strip()
    if len(text) < 10:
        raise DBError("Please write at least 10 characters in your review.")
    if len(text) > 1000:
        raise DBError("Reviews are limited to 1000 characters.")
    with transaction():
        if not query_one("SELECT 1 AS x FROM product WHERE product_id = :p AND is_active = 1", p=product_id):
            raise DBError("Product not found.")
        if user_review(user_id, product_id):
            raise DBError("You have already reviewed this product.")
        verified = 1 if has_purchased(user_id, product_id) else 0
        execute("""INSERT INTO review (product_id, user_id, rating, title, review_text, is_verified, data_origin)
                   VALUES (:p, :u, :r, :t, :x, :v, 'LIVE')""",
                p=product_id, u=user_id, r=rating, t=title or None, x=text, v=verified)
