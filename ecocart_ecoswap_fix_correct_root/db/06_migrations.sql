-- =============================================================================
-- EcoCart | 06_migrations.sql  (run as ECOCART)
-- Safe, idempotent migration for an EXISTING ECOCART schema.
-- It never drops tables or columns. For every column the application relies
-- on, it checks USER_TAB_COLUMNS and adds the column only if it is missing.
-- Run this if your tables were created before this version of the project
-- (e.g. an earlier import attempt) or if scripts/inspect_schema.py reports
-- missing columns. On a fresh install created by 01_schema.sql it is a no-op.
-- =============================================================================
SET SERVEROUTPUT ON

DECLARE
  -- Each entry: TABLE|COLUMN|DDL  (plain strings: works on every PL/SQL version)
  TYPE t_list IS TABLE OF VARCHAR2(400);
  v_cols t_list := t_list(
    'CATEGORY|SLUG|VARCHAR2(80)',
    'CATEGORY|DESCRIPTION|VARCHAR2(400)',
    'CATEGORY|ICON|VARCHAR2(40)',
    'CATEGORY|CREATED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL',
    'APP_USER|PHONE|VARCHAR2(20)',
    'APP_USER|ADDRESS_LINE|VARCHAR2(240)',
    'APP_USER|CITY|VARCHAR2(80)',
    'APP_USER|STATE|VARCHAR2(80)',
    'APP_USER|PINCODE|VARCHAR2(10)',
    'APP_USER|ROLE|VARCHAR2(20) DEFAULT ''CUSTOMER'' NOT NULL',
    'APP_USER|IS_DEMO|NUMBER(1) DEFAULT 0 NOT NULL',
    'APP_USER|DATA_ORIGIN|VARCHAR2(20) DEFAULT ''LIVE'' NOT NULL',
    'APP_USER|CREATED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL',
    'PRODUCT|BRAND|VARCHAR2(80)',
    'PRODUCT|DESCRIPTION|VARCHAR2(1000)',
    'PRODUCT|IMAGE_URL|VARCHAR2(400)',
    'PRODUCT|IS_ACTIVE|NUMBER(1) DEFAULT 1 NOT NULL',
    'PRODUCT|IS_FEATURED|NUMBER(1) DEFAULT 0 NOT NULL',
    'PRODUCT|DATA_ORIGIN|VARCHAR2(20) DEFAULT ''LIVE'' NOT NULL',
    'PRODUCT|SOURCE_KEY|VARCHAR2(80)',
    'PRODUCT|CREATED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL',
    'PRODUCT_SUSTAINABILITY|RECYCLABILITY_PCT|NUMBER(5,2)',
    'PRODUCT_SUSTAINABILITY|CARBON_FOOTPRINT_KG|NUMBER(8,3)',
    'PRODUCT_SUSTAINABILITY|CARBON_FOOTPRINT_UNIT|VARCHAR2(80)',
    'PRODUCT_SUSTAINABILITY|SUSTAINABILITY_EXPLANATION|VARCHAR2(600)',
    'PRODUCT_SUSTAINABILITY|SCORE_SOURCE|VARCHAR2(200)',
    'PRODUCT_SUSTAINABILITY|DATA_ORIGIN|VARCHAR2(20) DEFAULT ''LIVE'' NOT NULL',
    'PRODUCT_SUSTAINABILITY|UPDATED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL',
    'CART|STATUS|VARCHAR2(20) DEFAULT ''ACTIVE'' NOT NULL',
    'CART|CREATED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL',
    'CART|UPDATED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL',
    'CART_ITEM|ADDED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL',
    'CUSTOMER_ORDER|ORDER_REF|VARCHAR2(30)',
    'CUSTOMER_ORDER|SUBTOTAL|NUMBER(12,2) DEFAULT 0 NOT NULL',
    'CUSTOMER_ORDER|SHIPPING_FEE|NUMBER(10,2) DEFAULT 0 NOT NULL',
    'CUSTOMER_ORDER|SHIPPING_ADDRESS|VARCHAR2(400)',
    'CUSTOMER_ORDER|DATA_ORIGIN|VARCHAR2(20) DEFAULT ''LIVE'' NOT NULL',
    'CUSTOMER_ORDER|SOURCE_KEY|VARCHAR2(80)',
    'ORDER_ITEM|LINE_TOTAL|NUMBER(12,2)',
    'PAYMENT|TRANSACTION_REF|VARCHAR2(60)',
    'PAYMENT|PAID_AT|TIMESTAMP',
    'PAYMENT|CREATED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL',
    'REVIEW|TITLE|VARCHAR2(120)',
    'REVIEW|IS_VERIFIED|NUMBER(1) DEFAULT 0 NOT NULL',
    'REVIEW|DATA_ORIGIN|VARCHAR2(20) DEFAULT ''LIVE'' NOT NULL',
    'REVIEW|CREATED_AT|TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL'
  );
  v_tab VARCHAR2(30); v_col VARCHAR2(30); v_ddl VARCHAR2(400); v_n NUMBER; v_added NUMBER := 0;
BEGIN
  FOR i IN 1 .. v_cols.COUNT LOOP
    v_tab := SUBSTR(v_cols(i), 1, INSTR(v_cols(i), '|') - 1);
    v_col := SUBSTR(v_cols(i), INSTR(v_cols(i), '|') + 1, INSTR(v_cols(i), '|', 1, 2) - INSTR(v_cols(i), '|') - 1);
    v_ddl := SUBSTR(v_cols(i), INSTR(v_cols(i), '|', 1, 2) + 1);
    SELECT COUNT(*) INTO v_n FROM user_tab_columns WHERE table_name = v_tab AND column_name = v_col;
    IF v_n = 0 THEN
      EXECUTE IMMEDIATE 'ALTER TABLE ' || v_tab || ' ADD ' || v_col || ' ' || v_ddl;
      DBMS_OUTPUT.PUT_LINE('Added ' || v_tab || '.' || v_col);
      v_added := v_added + 1;
    END IF;
  END LOOP;
  DBMS_OUTPUT.PUT_LINE('Migration complete. Columns added: ' || v_added);
END;
/

-- Widen this existing column as well as defining it correctly in 01_schema.sql.
-- Seed data includes unit labels longer than the original VARCHAR2(30).
ALTER TABLE product_sustainability MODIFY (carbon_footprint_unit VARCHAR2(80));

-- Back-fill derived columns that may be NULL on legacy rows.
UPDATE order_item SET line_total = quantity * unit_price WHERE line_total IS NULL;
UPDATE customer_order o SET subtotal = NVL((SELECT SUM(line_total) FROM order_item oi WHERE oi.order_id = o.order_id), 0) WHERE subtotal = 0 AND total_amount > 0;
UPDATE customer_order SET order_ref = 'EC-LEGACY-' || LPAD(order_id, 6, '0') WHERE order_ref IS NULL;
UPDATE category SET slug = LOWER(REGEXP_REPLACE(category_name, '[^A-Za-z0-9]+', '-')) WHERE slug IS NULL;
COMMIT;

-- Add constraints that may be missing on legacy tables (ignored if they already exist).
DECLARE
  PROCEDURE try(p_sql VARCHAR2) IS
  BEGIN
    EXECUTE IMMEDIATE p_sql;
    DBMS_OUTPUT.PUT_LINE('Applied: ' || p_sql);
  EXCEPTION WHEN OTHERS THEN
    IF SQLCODE IN (-2264, -2261, -2275, -1442, -1451, -2260) THEN NULL;   -- already exists
    ELSE DBMS_OUTPUT.PUT_LINE('Skipped (' || SQLCODE || '): ' || p_sql); END IF;
  END;
BEGIN
  try('ALTER TABLE customer_order ADD CONSTRAINT uq_customer_order_ref UNIQUE (order_ref)');
  try('ALTER TABLE product_sustainability ADD CONSTRAINT uq_sustainability_prod UNIQUE (product_id)');
  try('ALTER TABLE cart_item ADD CONSTRAINT uq_cart_item UNIQUE (cart_id, product_id)');
  try('ALTER TABLE order_item ADD CONSTRAINT uq_order_item UNIQUE (order_id, product_id)');
  try('ALTER TABLE payment ADD CONSTRAINT uq_payment_order UNIQUE (order_id)');
  try('ALTER TABLE review ADD CONSTRAINT uq_review_user_prod UNIQUE (product_id, user_id)');
  try('ALTER TABLE review ADD CONSTRAINT ck_review_rating CHECK (rating BETWEEN 1 AND 5)');
  try('ALTER TABLE product ADD CONSTRAINT ck_product_stock CHECK (stock_quantity >= 0)');
  try('ALTER TABLE product_sustainability ADD CONSTRAINT ck_sustainability_score CHECK (eco_score BETWEEN 0 AND 100)');
END;
/
