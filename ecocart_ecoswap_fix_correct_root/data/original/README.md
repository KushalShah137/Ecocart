# Original dataset drop-folder

Place the CSV files of the **Indian E-Commerce Sales & Customer Analytics** dataset here
(`customers.csv`, `products.csv`, `orders.csv`, optionally `order_items.csv`) and run:

```bash
python scripts/import_dataset.py --dir data/original --dry-run   # report only
python scripts/import_dataset.py --dir data/original             # import
```

Status at project hand-over: the dataset was **not available** in the build environment
(the earlier import attempt had already failed because `customers.csv` was missing), so
nothing from it is in the seeded database. All rows in the database are `DATA_ORIGIN = 'SYNTHETIC'`
until an import succeeds, after which imported rows carry `DATA_ORIGIN = 'ORIGINAL'` and remain
distinguishable in every view and report. Orders whose customer is missing are rejected and counted
in the import report rather than invented.
