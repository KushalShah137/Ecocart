-- =============================================================================
-- EcoCart | 04_plsql.sql  (run as ECOCART)
-- Functions, the ECOCART_PKG package (order placement, cancellation, Eco Swap)
-- and the single justified trigger. Each block ends with "/" so the file runs
-- in SQL Developer, SQL*Plus, SQLcl and scripts/init_db.py.
--
-- Transaction policy: the package NEVER commits. The caller (Flask or your SQL
-- client) commits on success and rolls back on error, so an order, its items,
-- the stock reduction and the payment record are always all-or-nothing.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Eco-Score methodology v1 (documented in README):
--   eco_score = 0.40 * material_score + 0.25 * packaging_score
--             + 0.20 * recyclability_pct + 0.15 * durability_score
-- Every component is on a 0-100 scale. Rows produced by this formula from
-- assumed inputs are marked DATA_ORIGIN = 'SYNTHETIC'.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_compute_eco_score (
  p_material_score   IN NUMBER,
  p_packaging_score  IN NUMBER,
  p_recyclability    IN NUMBER,
  p_durability_score IN NUMBER
) RETURN NUMBER DETERMINISTIC IS
  v NUMBER;
BEGIN
  v := 0.40 * NVL(p_material_score, 0)
     + 0.25 * NVL(p_packaging_score, 0)
     + 0.20 * NVL(p_recyclability, 0)
     + 0.15 * NVL(p_durability_score, 0);
  RETURN LEAST(100, GREATEST(0, ROUND(v)));
END fn_compute_eco_score;
/

CREATE OR REPLACE FUNCTION fn_eco_grade (p_score IN NUMBER) RETURN VARCHAR2 DETERMINISTIC IS
BEGIN
  IF p_score IS NULL THEN RETURN 'N/A';
  ELSIF p_score >= 80 THEN RETURN 'A';
  ELSIF p_score >= 65 THEN RETURN 'B';
  ELSIF p_score >= 50 THEN RETURN 'C';
  ELSIF p_score >= 35 THEN RETURN 'D';
  ELSE RETURN 'E';
  END IF;
END fn_eco_grade;
/

CREATE OR REPLACE FUNCTION fn_product_avg_rating (p_product_id IN NUMBER) RETURN NUMBER IS
  v NUMBER;
BEGIN
  SELECT ROUND(AVG(rating), 2) INTO v FROM review WHERE product_id = p_product_id;
  RETURN v;
END fn_product_avg_rating;
/

CREATE OR REPLACE FUNCTION fn_cart_total (p_cart_id IN NUMBER) RETURN NUMBER IS
  v NUMBER;
BEGIN
  SELECT NVL(SUM(ci.quantity * p.price), 0) INTO v
  FROM cart_item ci JOIN product p ON p.product_id = ci.product_id
  WHERE ci.cart_id = p_cart_id;
  RETURN v;
END fn_cart_total;
/

-- Shipping rule used by both the website and historical seed data.
CREATE OR REPLACE FUNCTION fn_shipping_fee (p_subtotal IN NUMBER) RETURN NUMBER DETERMINISTIC IS
BEGIN
  RETURN CASE WHEN p_subtotal >= 999 THEN 0 ELSE 49 END;
END fn_shipping_fee;
/

-- -----------------------------------------------------------------------------
-- Conservative Eco Swap compatibility classifier.
-- Returns a product-function group only when the name gives a reasonably
-- clear type. Unknown/ambiguous products return NULL and are not auto-matched.
-- This prevents category-level false positives such as tape -> notebook or
-- a live plant -> cocopeat grow bag.
CREATE OR REPLACE FUNCTION fn_product_swap_group (
  p_category_id IN NUMBER,
  p_product_name IN VARCHAR2
) RETURN VARCHAR2 DETERMINISTIC IS
  n VARCHAR2(4000) := LOWER(NVL(p_product_name, ''));
BEGIN
  -- Stationery and desk items: keep functionally different supplies separate.
  IF INSTR(n, 'notebook') > 0 OR INSTR(n, 'notepad') > 0 OR INSTR(n, 'journal') > 0 THEN RETURN 'notebook';
  ELSIF INSTR(n, 'tape') > 0 THEN RETURN 'adhesive_tape';
  ELSIF INSTR(n, 'pencil') > 0 THEN RETURN 'pencil';
  ELSIF INSTR(n, 'highlighter') > 0 THEN RETURN 'highlighter';
  ELSIF INSTR(n, 'marker') > 0 THEN RETURN 'marker';
  ELSIF INSTR(n, 'pen') > 0 THEN RETURN 'pen';
  ELSIF INSTR(n, 'copy paper') > 0 OR INSTR(n, 'printer paper') > 0 THEN RETURN 'printer_paper';

  -- Apparel.
  ELSIF INSTR(n, 't-shirt') > 0 OR INSTR(n, 'tshirt') > 0 OR INSTR(n, 'tee ') > 0 THEN RETURN 't_shirt';
  ELSIF INSTR(n, 'kurta') > 0 THEN RETURN 'kurta';
  ELSIF INSTR(n, 'formal shirt') > 0 OR INSTR(n, 'dress shirt') > 0 THEN RETURN 'formal_shirt';
  ELSIF INSTR(n, 'shorts') > 0 THEN RETURN 'shorts';
  ELSIF INSTR(n, 'vest') > 0 THEN RETURN 'vest';

  -- Bags/accessories.
  ELSIF INSTR(n, 'backpack') > 0 OR INSTR(n, 'laptop bag') > 0 THEN RETURN 'backpack';
  ELSIF INSTR(n, 'tote bag') > 0 OR INSTR(n, 'tote') > 0 THEN RETURN 'tote_bag';
  ELSIF INSTR(n, 'wallet') > 0 THEN RETURN 'wallet';
  ELSIF INSTR(n, 'belt') > 0 THEN RETURN 'belt';

  -- Electronics.
  ELSIF INSTR(n, 'led bulb') > 0 OR INSTR(n, 'bulb') > 0 THEN RETURN 'light_bulb';
  ELSIF INSTR(n, 'power bank') > 0 THEN RETURN 'power_bank';
  ELSIF INSTR(n, 'speaker') > 0 THEN RETURN 'speaker';
  ELSIF INSTR(n, 'earbud') > 0 OR INSTR(n, 'earphone') > 0 OR INSTR(n, 'headphone') > 0 THEN RETURN 'audio_headset';
  ELSIF INSTR(n, 'usb cable') > 0 OR INSTR(n, 'charging cable') > 0 OR INSTR(n, 'konnect l') > 0 THEN RETURN 'charging_cable';
  ELSIF INSTR(n, 'power adapter') > 0 OR INSTR(n, 'charger') > 0 THEN RETURN 'power_adapter';
  ELSIF INSTR(n, 'rechargeable aa batter') > 0 OR INSTR(n, 'alkaline aa batter') > 0 OR INSTR(n, 'battery') > 0 THEN RETURN 'battery';
  ELSIF INSTR(n, 'smart plug') > 0 THEN RETURN 'smart_plug';
  ELSIF INSTR(n, 'usb mouse') > 0 OR INSTR(n, 'wireless mouse') > 0 THEN RETURN 'computer_mouse';
  ELSIF INSTR(n, 'keyboard') > 0 THEN RETURN 'keyboard';
  ELSIF INSTR(n, 'flash drive') > 0 OR INSTR(n, 'pen drive') > 0 THEN RETURN 'flash_drive';

  -- Containers, drinkware and kitchenware.
  ELSIF INSTR(n, 'lunch box') > 0 OR INSTR(n, 'lunchbox') > 0 THEN RETURN 'lunch_box';
  ELSIF INSTR(n, 'water bottle') > 0 OR INSTR(n, 'eco bottle') > 0 OR INSTR(n, 'copper bottle') > 0 THEN RETURN 'water_bottle';
  ELSIF INSTR(n, 'flask') > 0 OR INSTR(n, 'thermosteel') > 0 THEN RETURN 'flask';
  ELSIF INSTR(n, 'tumbler') > 0 OR INSTR(n, 'travel mug') > 0 OR INSTR(n, 'coffee mug') > 0 THEN RETURN 'travel_drinkware';
  ELSIF INSTR(n, 'straw') > 0 THEN RETURN 'drinking_straw';
  ELSIF INSTR(n, 'storage container') > 0 OR INSTR(n, 'food container') > 0 OR INSTR(n, 'modular mate') > 0 THEN RETURN 'food_storage_container';
  ELSIF INSTR(n, 'pressure cooker') > 0 THEN RETURN 'pressure_cooker';
  ELSIF INSTR(n, 'fry pan') > 0 OR INSTR(n, 'tawa') > 0 THEN RETURN 'frying_pan';
  ELSIF INSTR(n, 'mixing bowl') > 0 THEN RETURN 'mixing_bowl';

  -- Personal care.
  ELSIF INSTR(n, 'toothbrush') > 0 THEN RETURN 'toothbrush';
  ELSIF INSTR(n, 'toothpaste') > 0 THEN RETURN 'toothpaste';
  ELSIF INSTR(n, 'shampoo') > 0 THEN RETURN 'shampoo';
  ELSIF INSTR(n, 'soap') > 0 THEN RETURN 'soap';
  ELSIF INSTR(n, 'deodorant') > 0 THEN RETURN 'deodorant';

  -- Gardening: explicitly distinguish living plants from growing media/tools.
  ELSIF INSTR(n, 'artificial plant') > 0 THEN RETURN 'artificial_plant';
  ELSIF INSTR(n, 'seedling pot') > 0 THEN RETURN 'seedling_pot';
  ELSIF INSTR(n, 'plant pot') > 0 OR INSTR(n, 'plant planter') > 0 THEN RETURN 'plant_pot';
  ELSIF INSTR(n, 'grow bag') > 0 OR INSTR(n, 'cocopeat') > 0 OR INSTR(n, 'coco coir') > 0 THEN RETURN 'growing_medium';
  ELSIF INSTR(n, 'grow kit') > 0 OR INSTR(n, 'gardening kit') > 0 THEN RETURN 'gardening_kit';
  ELSIF INSTR(n, 'money plant') > 0 OR INSTR(n, 'succulent plant') > 0 OR INSTR(n, 'indoor plant') > 0 THEN RETURN 'live_plant';
  ELSIF INSTR(n, 'composting bin') > 0 THEN RETURN 'compost_bin';
  ELSIF INSTR(n, 'garbage bag') > 0 OR INSTR(n, 'bin liner') > 0 THEN RETURN 'garbage_bag';
  ELSIF INSTR(n, 'vermicompost') > 0 OR INSTR(n, 'compost') > 0 THEN RETURN 'compost';
  ELSIF INSTR(n, 'garden tool') > 0 THEN RETURN 'garden_tool_set';

  RETURN NULL;
END fn_product_swap_group;
/

-- -----------------------------------------------------------------------------
CREATE OR REPLACE PACKAGE ecocart_pkg AS
  -- Error codes raised by the package
  e_empty_cart        EXCEPTION; PRAGMA EXCEPTION_INIT(e_empty_cart,        -20010);
  e_out_of_stock      EXCEPTION; PRAGMA EXCEPTION_INIT(e_out_of_stock,      -20011);
  e_inactive_product  EXCEPTION; PRAGMA EXCEPTION_INIT(e_inactive_product,  -20012);
  e_bad_quantity      EXCEPTION; PRAGMA EXCEPTION_INIT(e_bad_quantity,      -20013);
  e_payment_declined  EXCEPTION; PRAGMA EXCEPTION_INIT(e_payment_declined,  -20030);
  e_not_authorised    EXCEPTION; PRAGMA EXCEPTION_INIT(e_not_authorised,    -20040);
  e_not_cancellable   EXCEPTION; PRAGMA EXCEPTION_INIT(e_not_cancellable,   -20041);

  c_default_tolerance CONSTANT NUMBER := 0.20;   -- Eco Swap ±20 % price window

  -- Checkout: converts the user's ACTIVE cart into an order atomically.
  PROCEDURE place_order (
    p_user_id          IN  NUMBER,
    p_payment_method   IN  VARCHAR2,          -- COD | DEMO_UPI | DEMO_CARD | DEMO_WALLET
    p_shipping_address IN  VARCHAR2,
    p_simulate_failure IN  NUMBER DEFAULT 0,  -- 1 = demo payment gateway declines
    p_order_id         OUT NUMBER,
    p_order_ref        OUT VARCHAR2
  );

  -- Cancels an order owned by the user, restores stock and refunds the demo payment.
  PROCEDURE cancel_order (p_order_id IN NUMBER, p_user_id IN NUMBER);

  -- Eco Swap: same recognized product function, higher Eco-Score, similar price, in stock.
  -- Unknown product types are excluded rather than matched by broad category alone.
  FUNCTION eco_swap (
    p_product_id IN NUMBER,
    p_tolerance  IN NUMBER DEFAULT c_default_tolerance,
    p_max_rows   IN NUMBER DEFAULT 4
  ) RETURN SYS_REFCURSOR;

  -- Safe stock adjustment used by admin/import scripts (delta may be negative).
  PROCEDURE adjust_stock (p_product_id IN NUMBER, p_delta IN NUMBER);
END ecocart_pkg;
/

CREATE OR REPLACE PACKAGE BODY ecocart_pkg AS

  FUNCTION next_order_ref RETURN VARCHAR2 IS
  BEGIN
    RETURN 'EC-' || TO_CHAR(SYSDATE, 'YYYYMMDD') || '-' ||
           TO_CHAR(TRUNC(DBMS_RANDOM.VALUE(0, 999999)), 'FM000000');
  END next_order_ref;

  PROCEDURE adjust_stock (p_product_id IN NUMBER, p_delta IN NUMBER) IS
    v_stock NUMBER;
  BEGIN
    SELECT stock_quantity INTO v_stock FROM product WHERE product_id = p_product_id FOR UPDATE;
    IF v_stock + p_delta < 0 THEN
      RAISE_APPLICATION_ERROR(-20011, 'Insufficient stock for product ' || p_product_id);
    END IF;
    UPDATE product SET stock_quantity = stock_quantity + p_delta WHERE product_id = p_product_id;
  END adjust_stock;

  PROCEDURE place_order (
    p_user_id          IN  NUMBER,
    p_payment_method   IN  VARCHAR2,
    p_shipping_address IN  VARCHAR2,
    p_simulate_failure IN  NUMBER DEFAULT 0,
    p_order_id         OUT NUMBER,
    p_order_ref        OUT VARCHAR2
  ) IS
    v_cart_id    NUMBER;
    v_subtotal   NUMBER := 0;
    v_shipping   NUMBER;
    v_pay_status VARCHAR2(20);
    v_ord_status VARCHAR2(20);
    v_ref        VARCHAR2(30);
    v_attempts   NUMBER := 0;

    CURSOR c_items IS
      SELECT ci.product_id, ci.quantity
      FROM cart_item ci
      WHERE ci.cart_id = v_cart_id
      ORDER BY ci.product_id;         -- deterministic lock order avoids deadlocks
  BEGIN
    -- 1. Locate and lock the active cart (one per user).
    BEGIN
      SELECT cart_id INTO v_cart_id
      FROM cart WHERE user_id = p_user_id AND status = 'ACTIVE'
      FOR UPDATE;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      RAISE_APPLICATION_ERROR(-20010, 'Your cart is empty.');
    END;

    -- 2. Validate every line, lock each product row, compute trusted subtotal.
    FOR r IN c_items LOOP
      DECLARE
        v_price  NUMBER; v_stock NUMBER; v_active NUMBER; v_name VARCHAR2(160);
      BEGIN
        SELECT price, stock_quantity, is_active, product_name
        INTO v_price, v_stock, v_active, v_name
        FROM product WHERE product_id = r.product_id FOR UPDATE;

        IF v_active <> 1 THEN
          RAISE_APPLICATION_ERROR(-20012, v_name || ' is no longer available.');
        END IF;
        IF r.quantity < 1 OR r.quantity > 50 THEN
          RAISE_APPLICATION_ERROR(-20013, 'Invalid quantity for ' || v_name);
        END IF;
        IF v_stock < r.quantity THEN
          RAISE_APPLICATION_ERROR(-20011, 'Only ' || v_stock || ' unit(s) of ' || v_name || ' left in stock.');
        END IF;
        v_subtotal := v_subtotal + ROUND(v_price * r.quantity, 2);
      END;
    END LOOP;

    IF v_subtotal = 0 THEN
      RAISE_APPLICATION_ERROR(-20010, 'Your cart is empty.');
    END IF;

    v_shipping := fn_shipping_fee(v_subtotal);

    -- 3. Simulated payment gateway. COD is collected later; demo methods settle now.
    IF p_payment_method = 'COD' THEN
      v_pay_status := 'PENDING'; v_ord_status := 'PLACED';
    ELSIF p_payment_method IN ('DEMO_UPI', 'DEMO_CARD', 'DEMO_WALLET') THEN
      IF p_simulate_failure = 1 THEN
        RAISE_APPLICATION_ERROR(-20030, 'Demo payment declined by simulated gateway.');
      END IF;
      v_pay_status := 'PAID'; v_ord_status := 'CONFIRMED';
    ELSE
      RAISE_APPLICATION_ERROR(-20030, 'Unsupported payment method: ' || p_payment_method);
    END IF;

    -- 4. Create the order (retry on the astronomically unlikely order_ref collision).
    LOOP
      v_ref := next_order_ref;
      BEGIN
        INSERT INTO customer_order (order_ref, user_id, status, subtotal, shipping_fee, total_amount, shipping_address, data_origin)
        VALUES (v_ref, p_user_id, v_ord_status, v_subtotal, v_shipping, v_subtotal + v_shipping, p_shipping_address, 'LIVE')
        RETURNING order_id INTO p_order_id;
        EXIT;
      EXCEPTION WHEN DUP_VAL_ON_INDEX THEN
        v_attempts := v_attempts + 1;
        IF v_attempts > 5 THEN RAISE; END IF;
      END;
    END LOOP;
    p_order_ref := v_ref;

    -- 5. Order items at purchase-time prices + stock reduction (rows already locked).
    INSERT INTO order_item (order_id, product_id, quantity, unit_price, line_total)
    SELECT p_order_id, ci.product_id, ci.quantity, p.price, ROUND(p.price * ci.quantity, 2)
    FROM cart_item ci JOIN product p ON p.product_id = ci.product_id
    WHERE ci.cart_id = v_cart_id;

    UPDATE product p
    SET    p.stock_quantity = p.stock_quantity - (SELECT ci.quantity FROM cart_item ci WHERE ci.cart_id = v_cart_id AND ci.product_id = p.product_id)
    WHERE  p.product_id IN (SELECT product_id FROM cart_item WHERE cart_id = v_cart_id);

    -- 6. Exactly one payment record per order (UQ_PAYMENT_ORDER prevents duplicates).
    INSERT INTO payment (order_id, payment_method, amount, status, transaction_ref, paid_at)
    VALUES (p_order_id, p_payment_method, v_subtotal + v_shipping, v_pay_status,
            CASE WHEN v_pay_status = 'PAID' THEN 'DEMO-' || v_ref ELSE NULL END,
            CASE WHEN v_pay_status = 'PAID' THEN SYSTIMESTAMP ELSE NULL END);

    -- 7. Close the cart.
    UPDATE cart SET status = 'CHECKED_OUT', updated_at = SYSTIMESTAMP WHERE cart_id = v_cart_id;
    -- No COMMIT here: the caller commits (see header).
  END place_order;

  PROCEDURE cancel_order (p_order_id IN NUMBER, p_user_id IN NUMBER) IS
    v_owner  NUMBER; v_status VARCHAR2(20);
  BEGIN
    SELECT user_id, status INTO v_owner, v_status
    FROM customer_order WHERE order_id = p_order_id FOR UPDATE;

    IF v_owner <> p_user_id THEN
      RAISE_APPLICATION_ERROR(-20040, 'You are not allowed to modify this order.');
    END IF;
    IF v_status NOT IN ('PLACED', 'CONFIRMED') THEN
      RAISE_APPLICATION_ERROR(-20041, 'Order can no longer be cancelled (status ' || v_status || ').');
    END IF;

    FOR r IN (SELECT product_id, quantity FROM order_item WHERE order_id = p_order_id ORDER BY product_id) LOOP
      adjust_stock(r.product_id, r.quantity);          -- restore inventory
    END LOOP;

    UPDATE customer_order SET status = 'CANCELLED' WHERE order_id = p_order_id;
    UPDATE payment SET status = CASE WHEN status = 'PAID' THEN 'REFUNDED' ELSE 'FAILED' END
    WHERE order_id = p_order_id AND status IN ('PAID', 'PENDING');
  EXCEPTION WHEN NO_DATA_FOUND THEN
    RAISE_APPLICATION_ERROR(-20040, 'Order not found.');
  END cancel_order;

  FUNCTION eco_swap (
    p_product_id IN NUMBER,
    p_tolerance  IN NUMBER DEFAULT c_default_tolerance,
    p_max_rows   IN NUMBER DEFAULT 4
  ) RETURN SYS_REFCURSOR IS
    rc SYS_REFCURSOR;
  BEGIN
    OPEN rc FOR
      SELECT alt.product_id,
             alt.product_name,
             alt.brand,
             alt.price,
             alt.image_url,
             alt.stock_quantity,
             alt.eco_score,
             alt.eco_grade,
             alt.material,
             alt.packaging_type,
             alt.recyclability_pct,
             alt.sustainability_explanation,
             alt.avg_rating,
             alt.review_count,
             alt.eco_score - orig.eco_score AS score_gain,
             alt.price     - orig.price     AS price_diff,
             ROUND((alt.price - orig.price) / orig.price * 100, 1) AS price_diff_pct
      FROM v_product_catalog orig
      JOIN v_product_catalog alt
        ON  alt.category_id = orig.category_id
        AND alt.product_id <> orig.product_id
        AND fn_product_swap_group(orig.category_id, orig.product_name) IS NOT NULL
        AND fn_product_swap_group(alt.category_id, alt.product_name) =
            fn_product_swap_group(orig.category_id, orig.product_name)
        AND alt.eco_score  >  orig.eco_score
        AND alt.price BETWEEN orig.price * (1 - p_tolerance) AND orig.price * (1 + p_tolerance)
        AND alt.stock_quantity > 0
        AND alt.is_active = 1
      WHERE orig.product_id = p_product_id
        AND orig.eco_score IS NOT NULL
      ORDER BY alt.eco_score DESC, ABS(alt.price - orig.price) ASC
      FETCH FIRST p_max_rows ROWS ONLY;
    RETURN rc;
  END eco_swap;

END ecocart_pkg;
/

-- -----------------------------------------------------------------------------
-- The only trigger: keep CART.UPDATED_AT current whenever items are added or
-- their quantity changes. Deletes are deliberately excluded so the ON DELETE
-- CASCADE from CART never hits a mutating-table error; the cart service stamps
-- UPDATED_AT itself on removal. (Stock, totals and statuses are handled inside
-- ECOCART_PKG transactions, so no triggers duplicate that logic.)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_cart_item_touch
AFTER INSERT OR UPDATE ON cart_item
FOR EACH ROW
BEGIN
  UPDATE cart SET updated_at = SYSTIMESTAMP WHERE cart_id = :NEW.cart_id;
END;
/
