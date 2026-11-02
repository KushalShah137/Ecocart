-- =============================================================================
-- EcoCart | 99_reset_data.sql  (run as ECOCART)  -- OPTIONAL, DESTRUCTIVE
-- Empties all ten tables (child tables first) WITHOUT dropping them, so you can
-- re-run 05_seed_data.sql from scratch. Nothing in the normal setup runs this.
-- =============================================================================
DELETE FROM review;
DELETE FROM payment;
DELETE FROM order_item;
DELETE FROM customer_order;
DELETE FROM cart_item;
DELETE FROM cart;
DELETE FROM product_sustainability;
DELETE FROM product;
DELETE FROM category;
DELETE FROM app_user;
COMMIT;
