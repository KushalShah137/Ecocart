-- =============================================================================
-- EcoCart | 03_views.sql  (run as ECOCART)
-- Views used by the Flask application and by the demo queries.
-- =============================================================================

-- 1. Catalogue view: product + category + sustainability + rating aggregates.
--    This is the single source for product cards everywhere in the site.
CREATE OR REPLACE VIEW v_product_catalog AS
SELECT
  p.product_id,
  p.product_name,
  p.brand,
  p.description,
  p.price,
  p.stock_quantity,
  p.image_url,
  p.is_active,
  p.is_featured,
  p.data_origin,
  p.created_at,
  c.category_id,
  c.category_name,
  c.slug                       AS category_slug,
  ps.eco_score,
  ps.material,
  ps.packaging_type,
  ps.recyclability_pct,
  ps.carbon_footprint_kg,
  ps.carbon_footprint_unit,
  ps.sustainability_explanation,
  ps.score_source,
  ps.data_origin               AS sustainability_origin,
  CASE
    WHEN ps.eco_score IS NULL THEN 'N/A'
    WHEN ps.eco_score >= 80   THEN 'A'
    WHEN ps.eco_score >= 65   THEN 'B'
    WHEN ps.eco_score >= 50   THEN 'C'
    WHEN ps.eco_score >= 35   THEN 'D'
    ELSE 'E'
  END                          AS eco_grade,
  r.review_count,
  r.avg_rating
FROM product p
JOIN category c ON c.category_id = p.category_id
LEFT JOIN product_sustainability ps ON ps.product_id = p.product_id
LEFT JOIN (
  SELECT product_id, COUNT(*) AS review_count, ROUND(AVG(rating), 2) AS avg_rating
  FROM review
  GROUP BY product_id
) r ON r.product_id = p.product_id;

-- 2. Order summary view: one row per order with item count and payment status.
CREATE OR REPLACE VIEW v_order_summary AS
SELECT
  o.order_id,
  o.order_ref,
  o.user_id,
  u.full_name                AS customer_name,
  u.email                    AS customer_email,
  o.order_date,
  o.status                   AS order_status,
  o.subtotal,
  o.shipping_fee,
  o.total_amount,
  o.data_origin,
  (SELECT COUNT(*)      FROM order_item oi WHERE oi.order_id = o.order_id) AS item_lines,
  (SELECT SUM(quantity) FROM order_item oi WHERE oi.order_id = o.order_id) AS item_units,
  pay.payment_method,
  pay.status                 AS payment_status,
  pay.transaction_ref,
  pay.paid_at
FROM customer_order o
JOIN app_user u ON u.user_id = o.user_id
LEFT JOIN payment pay ON pay.order_id = o.order_id;

-- 3. Category sustainability analytics.
CREATE OR REPLACE VIEW v_category_sustainability AS
SELECT
  c.category_id,
  c.category_name,
  c.slug,
  COUNT(p.product_id)                            AS product_count,
  COUNT(ps.sustainability_id)                    AS scored_products,
  ROUND(AVG(ps.eco_score), 1)                    AS avg_eco_score,
  MIN(ps.eco_score)                              AS min_eco_score,
  MAX(ps.eco_score)                              AS max_eco_score,
  ROUND(AVG(p.price), 2)                         AS avg_price
FROM category c
LEFT JOIN product p  ON p.category_id = c.category_id AND p.is_active = 1
LEFT JOIN product_sustainability ps ON ps.product_id = p.product_id
GROUP BY c.category_id, c.category_name, c.slug;

-- 4. Eco-Score band distribution (used by the dashboard histogram).
CREATE OR REPLACE VIEW v_eco_score_distribution AS
SELECT band, band_order, COUNT(*) AS product_count
FROM (
  SELECT
    CASE
      WHEN ps.eco_score >= 80 THEN '80-100'
      WHEN ps.eco_score >= 60 THEN '60-79'
      WHEN ps.eco_score >= 40 THEN '40-59'
      WHEN ps.eco_score >= 20 THEN '20-39'
      ELSE '0-19'
    END AS band,
    CASE
      WHEN ps.eco_score >= 80 THEN 5
      WHEN ps.eco_score >= 60 THEN 4
      WHEN ps.eco_score >= 40 THEN 3
      WHEN ps.eco_score >= 20 THEN 2
      ELSE 1
    END AS band_order
  FROM product_sustainability ps
  JOIN product p ON p.product_id = ps.product_id AND p.is_active = 1
)
GROUP BY band, band_order;

-- 5. Monthly sales trend (non-cancelled orders only).
CREATE OR REPLACE VIEW v_monthly_sales AS
SELECT
  TO_CHAR(o.order_date, 'YYYY-MM')  AS year_month,
  TRUNC(o.order_date, 'MM')         AS month_start,
  COUNT(*)                          AS order_count,
  SUM(o.total_amount)               AS revenue,
  ROUND(AVG(o.total_amount), 2)     AS avg_order_value
FROM customer_order o
WHERE o.status <> 'CANCELLED'
GROUP BY TO_CHAR(o.order_date, 'YYYY-MM'), TRUNC(o.order_date, 'MM');

-- 6. Popular products based on actual order records.
CREATE OR REPLACE VIEW v_popular_products AS
SELECT
  p.product_id,
  p.product_name,
  c.category_name,
  p.price,
  ps.eco_score,
  SUM(oi.quantity)      AS units_sold,
  SUM(oi.line_total)    AS revenue,
  COUNT(DISTINCT o.order_id) AS order_count
FROM order_item oi
JOIN customer_order o ON o.order_id = oi.order_id AND o.status <> 'CANCELLED'
JOIN product p        ON p.product_id = oi.product_id
JOIN category c       ON c.category_id = p.category_id
LEFT JOIN product_sustainability ps ON ps.product_id = p.product_id
GROUP BY p.product_id, p.product_name, c.category_name, p.price, ps.eco_score;

-- 7. Products missing sustainability data (incomplete-data report).
CREATE OR REPLACE VIEW v_missing_sustainability AS
SELECT p.product_id, p.product_name, p.brand, c.category_name, p.price, p.stock_quantity
FROM product p
JOIN category c ON c.category_id = p.category_id
WHERE NOT EXISTS (SELECT 1 FROM product_sustainability ps WHERE ps.product_id = p.product_id);
