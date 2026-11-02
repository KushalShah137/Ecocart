-- Run as ECOCART in XEPDB1 after applying db/04_plsql.sql.
-- Expected: distinct function groups; mismatched pairs must return zero rows.

SELECT
  fn_product_swap_group(1, 'Nayasa Reusable Water Bottle') AS bottle_group,
  fn_product_swap_group(1, 'Stainless Steel Reusable Straw Set') AS straw_group,
  fn_product_swap_group(1, 'Neem Oil Garden Spray') AS spray_group,
  fn_product_swap_group(1, 'Cocopeat Grow Bag') AS cocopeat_group,
  fn_product_swap_group(1, 'Ugaoo Money Plant') AS plant_group,
  fn_product_swap_group(1, 'IKEA FEJKA Artificial Plant') AS artificial_plant_group,
  fn_product_swap_group(1, 'Scotch Magic Tape') AS tape_group,
  fn_product_swap_group(1, 'Paperkraft Premium Notebook') AS notebook_group,
  fn_product_swap_group(1, 'Skybags Brat Backpack') AS backpack_group,
  fn_product_swap_group(1, 'Fastrack Sling Bag') AS sling_group
FROM dual;

SELECT name, type, line, position, text
FROM user_errors
WHERE name IN ('FN_PRODUCT_SWAP_GROUP', 'ECOCART_PKG')
ORDER BY name, sequence;
