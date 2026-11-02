EcoCart EcoSwap SQL compilation fix

Files in this patch are relative to your existing EcoCart project root:
- db/04_plsql.sql
- db/verify_ecoswap.sql
- ecocart/services/ecoswap.py (unchanged reference copy; no replacement needed unless desired)

Root cause found in db/04_plsql.sql:
The function had RETURN NULL; before END IF;, which is invalid PL/SQL block order.
The corrected order is END IF; RETURN NULL; END fn_product_swap_group;.
The product grouping rules already distinguish bottle/straw, live/artificial plant/growing medium,
garden spray/growing medium, tape/notebook, and backpack/sling bag.

Apply:
1. Back up db/04_plsql.sql.
2. Copy the patched db/04_plsql.sql into your project root, replacing the old file.
3. From project root run:
   .venv\Scripts\activate
   python scripts/init_db.py --only 04_plsql.sql
4. Check output for compilation errors. The script may report statement execution success even if
   Oracle compiled an object with errors, so verify in SQL Developer using db/verify_ecoswap.sql.
5. Restart Flask and hard-refresh /eco-swap (Ctrl+F5).

Expected verification groups:
water_bottle; drinking_straw; garden_spray; growing_medium; live_plant; artificial_plant;
adhesive_tape; notebook; backpack; sling_bag.
The USER_ERRORS query should return no rows for FN_PRODUCT_SWAP_GROUP or ECOCART_PKG.

Important observation:
The current uploaded project template's headline differs from the screenshot shown in chat.
If after this SQL fix the live page still shows the old recommendations, confirm that Flask is
running from this exact project folder; it may be launching another copy of the project.
