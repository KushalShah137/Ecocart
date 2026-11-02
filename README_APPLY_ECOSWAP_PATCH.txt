EcoCart EcoSwap teammate-logic patch
====================================

This is a targeted patch for the EXISTING project, not a complete project archive.
It contains only:
  db/04_plsql.sql
  ecocart/services/ecoswap.py

Apply:
1. Extract this ZIP directly into your project root:
   C:\Users\hp\Desktop\ecocart-project\ecocart
   Allow replacement of the two files above.
   Do NOT replace .env or .venv.
2. From that same project-root terminal, run:
   .venv\Scripts\activate
   python scripts/init_db.py --only 04_plsql.sql
3. Check the output for PL/SQL compilation errors. The previous function had a
   missing END IF; this patch includes it.
4. Restart Flask completely and refresh /eco-swap with Ctrl+F5.

What this does:
- Adds stricter product-function groups to the existing fn_product_swap_group
  function, using the teammate's same-product-type idea but keeping the original
  project's function name, package and schema.
- Applies the same product-type guard to the Oracle package EcoSwap and the
  homepage/showcase query (the package already had the guard; showcase is aligned).
- Keeps bottle vs straw, plant vs grow media, backpack vs sling bag, notebook vs
  drawing book, and tape vs notebook as distinct groups.
- Unknown product types return NULL and are not recommended.

This patch does not modify the catalogue, users, orders, .env, or virtual environment.
