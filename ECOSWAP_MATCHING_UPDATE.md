# EcoSwap matching update

## What changed

EcoSwap now requires a recognized product-function match in addition to the existing rules: the alternative must have a higher estimated Eco-Score, be within the configured price tolerance, and be active/in stock. The same classifier is used by product-page recommendations and the homepage EcoSwap showcase.

Examples:
- `Scotch Magic Tape` is classified as `adhesive_tape`; `Paperkraft Premium Notebook` is classified as `notebook`, so they cannot be paired.
- `Ugaoo Money Plant` is classified as `live_plant`; `Cocopeat Grow Bag` is classified as `growing_medium`, so they cannot be paired.
- A notebook can only be paired with another recognized notebook, and tape with other recognized tape.

Unknown or ambiguous product types return no group and are excluded instead of being guessed from the broad category. This may reduce the number of recommendations; that is intentional.

## Apply to your current database

From the project root, with the existing virtual environment active, run:

```bat
python scripts/init_db.py --only 04_plsql.sql
```

Then restart the Flask app. This updates/recompiles PL/SQL only. It does not rerun seed data, change passwords, or reset catalogue/user/order rows.

## Limitations

Matching is a conservative, deterministic name-rule classifier, not machine learning. New product types should be explicitly added to `FN_PRODUCT_SWAP_GROUP` in `db/04_plsql.sql`. Eco-Scores and prices remain illustrative dataset values.
