-- =============================================================================
-- EcoCart | demo_queries.sql  (run as ECOCART in SQL Developer / SQLcl / SQL*Plus)
-- Demonstration queries for the DBMS project review. Each section is numbered
-- and self-contained; run them one at a time or the whole file.
-- =============================================================================
SET LINESIZE 200 PAGESIZE 60
COLUMN product_name FORMAT A45
COLUMN category_name FORMAT A26
COLUMN full_name FORMAT A22
COLUMN email FORMAT A30

-- -----------------------------------------------------------------------------
-- 1. Schema overview: tables, constraints (PK / FK / UNIQUE / CHECK / NOT NULL)
-- -----------------------------------------------------------------------------
SELECT table_name, num_rows_hint
FROM (SELECT table_name, (SELECT COUNT(*) FROM user_tab_columns c WHERE c.table_name = t.table_name) AS num_rows_hint
      FROM user_tables t)
ORDER BY table_name;

SELECT table_name, constraint_name,
       CASE constraint_type WHEN 'P' THEN 'PRIMARY KEY' WHEN 'R' THEN 'FOREIGN KEY'
                            WHEN 'U' THEN 'UNIQUE' WHEN 'C' THEN 'CHECK / NOT NULL' END AS kind,
       search_condition_vc
FROM user_constraints
WHERE table_name IN ('APP_USER','CATEGORY','PRODUCT','PRODUCT_SUSTAINABILITY','CART','CART_ITEM',
                     'CUSTOMER_ORDER','ORDER_ITEM','PAYMENT','REVIEW')
ORDER BY table_name, constraint_type, constraint_name;

-- Row counts per table (data provenance is tracked in DATA_ORIGIN)
SELECT 'APP_USER' t, COUNT(*) n FROM app_user UNION ALL SELECT 'CATEGORY', COUNT(*) FROM category
UNION ALL SELECT 'PRODUCT', COUNT(*) FROM product UNION ALL SELECT 'PRODUCT_SUSTAINABILITY', COUNT(*) FROM product_sustainability
UNION ALL SELECT 'CART', COUNT(*) FROM cart UNION ALL SELECT 'CART_ITEM', COUNT(*) FROM cart_item
UNION ALL SELECT 'CUSTOMER_ORDER', COUNT(*) FROM customer_order UNION ALL SELECT 'ORDER_ITEM', COUNT(*) FROM order_item
UNION ALL SELECT 'PAYMENT', COUNT(*) FROM payment UNION ALL SELECT 'REVIEW', COUNT(*) FROM review;

SELECT data_origin, COUNT(*) AS orders FROM customer_order GROUP BY data_origin;

-- -----------------------------------------------------------------------------
-- 2. Multi-table join: product catalogue with category, Eco-Score and ratings
-- -----------------------------------------------------------------------------
SELECT p.product_id, p.product_name, c.category_name, p.price, ps.eco_score,
       fn_eco_grade(ps.eco_score) AS grade, fn_product_avg_rating(p.product_id) AS avg_rating
FROM product p
JOIN category c ON c.category_id = p.category_id
LEFT JOIN product_sustainability ps ON ps.product_id = p.product_id
ORDER BY ps.eco_score DESC NULLS LAST
FETCH FIRST 15 ROWS ONLY;

-- -----------------------------------------------------------------------------
-- 3. GROUP BY + HAVING + aggregates: categories whose average Eco-Score is >= 60
-- -----------------------------------------------------------------------------
SELECT c.category_name,
       COUNT(p.product_id)            AS products,
       COUNT(ps.sustainability_id)    AS scored,
       ROUND(AVG(ps.eco_score), 1)    AS avg_eco,
       MIN(ps.eco_score)              AS min_eco,
       MAX(ps.eco_score)              AS max_eco,
       ROUND(AVG(p.price), 2)         AS avg_price
FROM category c
JOIN product p ON p.category_id = c.category_id
LEFT JOIN product_sustainability ps ON ps.product_id = p.product_id
GROUP BY c.category_name
HAVING AVG(ps.eco_score) >= 60
ORDER BY avg_eco DESC;

-- -----------------------------------------------------------------------------
-- 4. CASE expression: Eco-Score band distribution (same logic as the dashboard)
-- -----------------------------------------------------------------------------
SELECT CASE WHEN eco_score >= 80 THEN '80-100 (A)'
            WHEN eco_score >= 65 THEN '65-79  (B)'
            WHEN eco_score >= 50 THEN '50-64  (C)'
            WHEN eco_score >= 35 THEN '35-49  (D)'
            ELSE                      '0-34   (E)' END AS band,
       COUNT(*) AS products,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM product_sustainability
GROUP BY CASE WHEN eco_score >= 80 THEN '80-100 (A)' WHEN eco_score >= 65 THEN '65-79  (B)'
              WHEN eco_score >= 50 THEN '50-64  (C)' WHEN eco_score >= 35 THEN '35-49  (D)' ELSE '0-34   (E)' END
ORDER BY band DESC;

-- -----------------------------------------------------------------------------
-- 5. Nested subquery: products priced above their category's average price
-- -----------------------------------------------------------------------------
SELECT p.product_name, c.category_name, p.price,
       (SELECT ROUND(AVG(price), 2) FROM product x WHERE x.category_id = p.category_id) AS category_avg
FROM product p JOIN category c ON c.category_id = p.category_id
WHERE p.price > (SELECT AVG(price) FROM product x WHERE x.category_id = p.category_id)
ORDER BY c.category_name, p.price DESC;

-- -----------------------------------------------------------------------------
-- 6. Correlated subquery + EXISTS: customers who bought at least one grade-A product
-- -----------------------------------------------------------------------------
SELECT u.user_id, u.full_name, u.city
FROM app_user u
WHERE EXISTS (
  SELECT 1 FROM customer_order o
  JOIN order_item oi ON oi.order_id = o.order_id
  JOIN product_sustainability ps ON ps.product_id = oi.product_id
  WHERE o.user_id = u.user_id AND o.status <> 'CANCELLED' AND ps.eco_score >= 80)
ORDER BY u.full_name;

-- -----------------------------------------------------------------------------
-- 7. NOT EXISTS: missing sustainability data report (incomplete-data case)
-- -----------------------------------------------------------------------------
SELECT p.product_id, p.product_name, c.category_name, p.price
FROM product p JOIN category c ON c.category_id = p.category_id
WHERE NOT EXISTS (SELECT 1 FROM product_sustainability ps WHERE ps.product_id = p.product_id)
ORDER BY c.category_name;
-- (equivalent view) SELECT * FROM v_missing_sustainability;

-- Products never ordered
SELECT p.product_name FROM product p
WHERE NOT EXISTS (SELECT 1 FROM order_item oi WHERE oi.product_id = p.product_id);

-- -----------------------------------------------------------------------------
-- 8. Customer purchase history (join across user, order, item, product, payment)
-- -----------------------------------------------------------------------------
SELECT u.full_name, o.order_ref, TO_CHAR(o.order_date, 'DD-Mon-YYYY') AS order_date, o.status,
       p.product_name, oi.quantity, oi.unit_price, oi.line_total, pay.payment_method, pay.status AS pay_status
FROM app_user u
JOIN customer_order o ON o.user_id = u.user_id
JOIN order_item oi ON oi.order_id = o.order_id
JOIN product p ON p.product_id = oi.product_id
JOIN payment pay ON pay.order_id = o.order_id
WHERE u.email = 'demo@example.com'
ORDER BY o.order_date DESC, oi.order_item_id;

-- -----------------------------------------------------------------------------
-- 9. Date-based analysis: monthly sales, orders and average order value
-- -----------------------------------------------------------------------------
SELECT TO_CHAR(order_date, 'YYYY-MM') AS month, COUNT(*) AS orders,
       SUM(total_amount) AS revenue, ROUND(AVG(total_amount), 2) AS avg_order_value
FROM customer_order
WHERE status <> 'CANCELLED' AND order_date >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -11)
GROUP BY TO_CHAR(order_date, 'YYYY-MM')
ORDER BY month;
-- (equivalent view) SELECT * FROM v_monthly_sales ORDER BY year_month;

-- Day-of-week ordering pattern
SELECT TO_CHAR(order_date, 'Day') AS weekday, COUNT(*) AS orders
FROM customer_order GROUP BY TO_CHAR(order_date, 'Day'), TO_CHAR(order_date, 'D') ORDER BY TO_CHAR(order_date, 'D');

-- -----------------------------------------------------------------------------
-- 10. Analytic functions: running revenue, rank of products within category by Eco-Score
-- -----------------------------------------------------------------------------
SELECT year_month, revenue,
       SUM(revenue) OVER (ORDER BY year_month) AS running_revenue,
       ROUND(100 * (revenue - LAG(revenue) OVER (ORDER BY year_month)) / NULLIF(LAG(revenue) OVER (ORDER BY year_month), 0), 1) AS mom_growth_pct
FROM v_monthly_sales ORDER BY year_month;

SELECT category_name, product_name, eco_score,
       RANK() OVER (PARTITION BY category_name ORDER BY eco_score DESC) AS eco_rank_in_category,
       ROUND(eco_score - AVG(eco_score) OVER (PARTITION BY category_name), 1) AS vs_category_avg
FROM v_product_catalog
WHERE eco_score IS NOT NULL
ORDER BY category_name, eco_rank_in_category
FETCH FIRST 24 ROWS ONLY;

-- -----------------------------------------------------------------------------
-- 11. Product rating summary (aggregates + HAVING on review count)
-- -----------------------------------------------------------------------------
SELECT p.product_name, COUNT(r.review_id) AS reviews, ROUND(AVG(r.rating), 2) AS avg_rating,
       SUM(CASE WHEN r.rating = 5 THEN 1 ELSE 0 END) AS five_star,
       SUM(CASE WHEN r.is_verified = 1 THEN 1 ELSE 0 END) AS verified
FROM product p JOIN review r ON r.product_id = p.product_id
GROUP BY p.product_name
HAVING COUNT(r.review_id) >= 2
ORDER BY avg_rating DESC, reviews DESC;

-- -----------------------------------------------------------------------------
-- 12. Sustainability comparison: conventional vs greener pairs in the same category
-- -----------------------------------------------------------------------------
SELECT a.product_name AS conventional, a.eco_score AS score_a, a.price AS price_a,
       b.product_name AS greener,     b.eco_score AS score_b, b.price AS price_b,
       b.eco_score - a.eco_score AS gain
FROM v_product_catalog a JOIN v_product_catalog b
  ON a.category_id = b.category_id AND b.eco_score - a.eco_score >= 40
 AND b.price BETWEEN a.price * 0.8 AND a.price * 1.2
ORDER BY gain DESC FETCH FIRST 12 ROWS ONLY;

-- -----------------------------------------------------------------------------
-- 13. Eco Swap — the recommendation query (plain SQL version of ECOCART_PKG.ECO_SWAP)
--     Original: Polyester Laptop Backpack 25L  (tolerance ±20 %)
-- -----------------------------------------------------------------------------
SELECT alt.product_id, alt.product_name, alt.price, alt.eco_score, alt.material, alt.packaging_type,
       alt.eco_score - orig.eco_score AS score_gain, alt.price - orig.price AS price_diff
FROM product orig
JOIN product_sustainability ops ON ops.product_id = orig.product_id
JOIN product alt ON alt.category_id = orig.category_id AND alt.product_id <> orig.product_id
JOIN product_sustainability ps ON ps.product_id = alt.product_id
WHERE orig.product_name = 'Polyester Laptop Backpack 25L'
  AND ps.eco_score > ops.eco_score
  AND alt.price BETWEEN orig.price * 0.80 AND orig.price * 1.20
  AND alt.stock_quantity > 0 AND alt.is_active = 1
ORDER BY ps.eco_score DESC, ABS(alt.price - orig.price) ASC;

-- Same thing through the PL/SQL package (returns a REF CURSOR)
DECLARE
  rc  SYS_REFCURSOR;
  v_id NUMBER; v_name VARCHAR2(160); v_brand VARCHAR2(80); v_price NUMBER; v_img VARCHAR2(400); v_stock NUMBER;
  v_score NUMBER; v_grade VARCHAR2(5); v_mat VARCHAR2(120); v_pkg VARCHAR2(80); v_rec NUMBER; v_expl VARCHAR2(600);
  v_rating NUMBER; v_rc NUMBER; v_gain NUMBER; v_diff NUMBER; v_pct NUMBER;
BEGIN
  SELECT product_id INTO v_id FROM product WHERE product_name = 'Polyester Laptop Backpack 25L';
  rc := ecocart_pkg.eco_swap(v_id, 0.20, 4);
  LOOP
    FETCH rc INTO v_id, v_name, v_brand, v_price, v_img, v_stock, v_score, v_grade, v_mat, v_pkg, v_rec, v_expl, v_rating, v_rc, v_gain, v_diff, v_pct;
    EXIT WHEN rc%NOTFOUND;
    DBMS_OUTPUT.PUT_LINE(v_name || ' | Eco ' || v_score || ' (+' || v_gain || ') | Rs ' || v_price || ' (' || v_diff || ')');
  END LOOP;
  CLOSE rc;
END;
/

-- Honest empty state: cheap plastic straws have no alternative inside ±20 %
DECLARE rc SYS_REFCURSOR; n NUMBER := 0; v_id NUMBER;
  v_name VARCHAR2(160); v_brand VARCHAR2(80); v_price NUMBER; v_img VARCHAR2(400); v_stock NUMBER;
  v_score NUMBER; v_grade VARCHAR2(5); v_mat VARCHAR2(120); v_pkg VARCHAR2(80); v_rec NUMBER; v_expl VARCHAR2(600);
  v_rating NUMBER; v_rc NUMBER; v_gain NUMBER; v_diff NUMBER; v_pct NUMBER;
BEGIN
  SELECT product_id INTO v_id FROM product WHERE product_name = 'Plastic Straws (100-pack)';
  rc := ecocart_pkg.eco_swap(v_id, 0.20, 4);
  LOOP FETCH rc INTO v_id, v_name, v_brand, v_price, v_img, v_stock, v_score, v_grade, v_mat, v_pkg, v_rec, v_expl, v_rating, v_rc, v_gain, v_diff, v_pct;
       EXIT WHEN rc%NOTFOUND; n := n + 1; END LOOP;
  CLOSE rc;
  DBMS_OUTPUT.PUT_LINE('Plastic straws: ' || n || ' alternatives within ±20% (expected 0 -> website shows an empty state)');
END;
/

-- -----------------------------------------------------------------------------
-- 14. Transaction demo: place an order through the package, inspect, then ROLLBACK
-- -----------------------------------------------------------------------------
SET SERVEROUTPUT ON
DECLARE
  v_user  NUMBER; v_cart NUMBER; v_prod NUMBER; v_stock_before NUMBER; v_stock_after NUMBER;
  v_order NUMBER; v_ref VARCHAR2(30);
BEGIN
  SELECT user_id INTO v_user FROM app_user WHERE email = 'demo@example.com';
  SELECT product_id, stock_quantity INTO v_prod, v_stock_before
  FROM product WHERE product_name = 'Stainless Steel Water Bottle 1L (insulated)';

  -- fresh active cart with 2 bottles
  DELETE FROM cart_item WHERE cart_id IN (SELECT cart_id FROM cart WHERE user_id = v_user AND status = 'ACTIVE');
  DELETE FROM cart WHERE user_id = v_user AND status = 'ACTIVE';
  INSERT INTO cart (user_id) VALUES (v_user) RETURNING cart_id INTO v_cart;
  INSERT INTO cart_item (cart_id, product_id, quantity) VALUES (v_cart, v_prod, 2);

  ecocart_pkg.place_order(v_user, 'DEMO_UPI', '12, MG Road, Vellore, Tamil Nadu - 632001', 0, v_order, v_ref);
  SELECT stock_quantity INTO v_stock_after FROM product WHERE product_id = v_prod;
  DBMS_OUTPUT.PUT_LINE('Order ' || v_ref || ' (#' || v_order || ') placed. Stock ' || v_stock_before || ' -> ' || v_stock_after);

  -- Demonstrate the payment-failure path: raises ORA-20030 and leaves nothing behind
  INSERT INTO cart (user_id) VALUES (v_user) RETURNING cart_id INTO v_cart;
  INSERT INTO cart_item (cart_id, product_id, quantity) VALUES (v_cart, v_prod, 1);
  BEGIN
    ecocart_pkg.place_order(v_user, 'DEMO_CARD', '12, MG Road, Vellore, Tamil Nadu - 632001', 1, v_order, v_ref);
  EXCEPTION WHEN ecocart_pkg.e_payment_declined THEN
    DBMS_OUTPUT.PUT_LINE('Declined as expected: ' || SQLERRM);
  END;
  SELECT stock_quantity INTO v_stock_after FROM product WHERE product_id = v_prod;
  DBMS_OUTPUT.PUT_LINE('Stock after declined attempt: ' || v_stock_after || ' (unchanged by the failed order)');

  ROLLBACK;   -- undo the demo so the seed data stays pristine
  DBMS_OUTPUT.PUT_LINE('Rolled back. Demo data unchanged.');
END;
/

-- -----------------------------------------------------------------------------
-- 15. Views in action
-- -----------------------------------------------------------------------------
SELECT * FROM v_category_sustainability ORDER BY avg_eco_score DESC NULLS LAST;
SELECT * FROM v_eco_score_distribution ORDER BY band_order;
SELECT product_name, units_sold, revenue, order_count FROM v_popular_products ORDER BY units_sold DESC FETCH FIRST 10 ROWS ONLY;
SELECT order_ref, customer_name, order_date, order_status, payment_method, payment_status, total_amount
FROM v_order_summary ORDER BY order_date DESC FETCH FIRST 10 ROWS ONLY;

-- -----------------------------------------------------------------------------
-- 16. Constraint demonstrations (each statement is expected to FAIL)
-- -----------------------------------------------------------------------------
-- CHECK: rating must be 1-5
INSERT INTO review (product_id, user_id, rating, review_text) VALUES (1, 1, 6, 'invalid rating');
-- FOREIGN KEY: product must exist
INSERT INTO product_sustainability (product_id, material, packaging_type, eco_score) VALUES (999999, 'x', 'y', 50);
-- UNIQUE: one review per customer per product (pick an existing pair)
INSERT INTO review (product_id, user_id, rating, review_text)
SELECT product_id, user_id, 4, 'duplicate' FROM review WHERE ROWNUM = 1;
-- CHECK: stock can never go negative
UPDATE product SET stock_quantity = -1 WHERE product_id = 1;
ROLLBACK;
