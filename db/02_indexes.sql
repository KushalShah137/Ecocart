-- =============================================================================
-- EcoCart | 02_indexes.sql  (run as ECOCART)
-- Secondary indexes supporting catalogue filtering, Eco Swap, carts, orders and
-- analytics. CREATE INDEX keeps the script re-runnable.
-- (Unique constraints and primary keys already create their own indexes.)
-- =============================================================================

-- Catalogue browsing and Eco Swap (category + price range + stock)
CREATE INDEX ix_product_category_price ON product (category_id, price);
CREATE INDEX ix_product_name_upper     ON product (UPPER(product_name));
CREATE INDEX ix_product_active_feat    ON product (is_active, is_featured);

-- Eco-Score filters / ordering
CREATE INDEX ix_sust_eco_score ON product_sustainability (eco_score);

-- Cart lookups
CREATE INDEX ix_cart_user_status ON cart (user_id, status);
CREATE INDEX ix_cart_item_product ON cart_item (product_id);

-- Order history and sales analytics
CREATE INDEX ix_order_user_date  ON customer_order (user_id, order_date DESC);
CREATE INDEX ix_order_date       ON customer_order (order_date);
CREATE INDEX ix_order_status     ON customer_order (status);
CREATE INDEX ix_order_item_prod  ON order_item (product_id);

-- Reviews per product
CREATE INDEX ix_review_product   ON review (product_id, created_at DESC);
