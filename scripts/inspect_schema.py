#!/usr/bin/env python3
"""
Prints what already exists in the ECOCART schema and which columns the
application needs that are missing. Run this BEFORE the SQL scripts on an
installation that already has the ten tables, then run db/06_migrations.sql
if anything is reported missing.

    python scripts/inspect_schema.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ecocart.db import get_connection  # noqa: E402

REQUIRED = {
    "CATEGORY": ["CATEGORY_ID", "CATEGORY_NAME", "SLUG", "DESCRIPTION", "ICON", "CREATED_AT"],
    "APP_USER": ["USER_ID", "FULL_NAME", "EMAIL", "PASSWORD_HASH", "PHONE", "ADDRESS_LINE", "CITY", "STATE", "PINCODE",
                 "ROLE", "IS_DEMO", "DATA_ORIGIN", "CREATED_AT"],
    "PRODUCT": ["PRODUCT_ID", "CATEGORY_ID", "PRODUCT_NAME", "BRAND", "DESCRIPTION", "PRICE", "STOCK_QUANTITY",
                "IMAGE_URL", "IS_ACTIVE", "IS_FEATURED", "DATA_ORIGIN", "SOURCE_KEY", "CREATED_AT"],
    "PRODUCT_SUSTAINABILITY": ["SUSTAINABILITY_ID", "PRODUCT_ID", "MATERIAL", "PACKAGING_TYPE", "RECYCLABILITY_PCT",
                               "ECO_SCORE", "CARBON_FOOTPRINT_KG", "CARBON_FOOTPRINT_UNIT", "SUSTAINABILITY_EXPLANATION",
                               "SCORE_SOURCE", "DATA_ORIGIN", "UPDATED_AT"],
    "CART": ["CART_ID", "USER_ID", "STATUS", "CREATED_AT", "UPDATED_AT"],
    "CART_ITEM": ["CART_ITEM_ID", "CART_ID", "PRODUCT_ID", "QUANTITY", "ADDED_AT"],
    "CUSTOMER_ORDER": ["ORDER_ID", "ORDER_REF", "USER_ID", "ORDER_DATE", "STATUS", "SUBTOTAL", "SHIPPING_FEE",
                       "TOTAL_AMOUNT", "SHIPPING_ADDRESS", "DATA_ORIGIN", "SOURCE_KEY"],
    "ORDER_ITEM": ["ORDER_ITEM_ID", "ORDER_ID", "PRODUCT_ID", "QUANTITY", "UNIT_PRICE", "LINE_TOTAL"],
    "PAYMENT": ["PAYMENT_ID", "ORDER_ID", "PAYMENT_METHOD", "AMOUNT", "STATUS", "TRANSACTION_REF", "PAID_AT", "CREATED_AT"],
    "REVIEW": ["REVIEW_ID", "PRODUCT_ID", "USER_ID", "RATING", "TITLE", "REVIEW_TEXT", "IS_VERIFIED", "DATA_ORIGIN", "CREATED_AT"],
}


def main():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
    tables = [r[0] for r in cur.fetchall()]
    print("Connected as", conn.username, "| tables:", ", ".join(tables) or "(none)")
    missing_tables, missing_cols = [], []
    for t, cols in REQUIRED.items():
        if t not in tables:
            missing_tables.append(t); continue
        cur.execute("SELECT column_name FROM user_tab_columns WHERE table_name = :t", t=t)
        have = {r[0] for r in cur.fetchall()}
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        n = cur.fetchone()[0]
        miss = [c for c in cols if c not in have]
        print(f"  {t:24} rows={n:<6} {'OK' if not miss else 'missing: ' + ', '.join(miss)}")
        missing_cols += [f"{t}.{c}" for c in miss]
    cur.execute("SELECT object_type, object_name, status FROM user_objects WHERE object_type IN ('VIEW','PACKAGE','PACKAGE BODY','FUNCTION','PROCEDURE','TRIGGER') ORDER BY 1,2")
    objs = cur.fetchall()
    print("Views / PL-SQL objects:", ", ".join(f"{o[1]}({o[2]})" for o in objs) or "(none)")
    print()
    if missing_tables:
        print("Missing tables (run db/01_schema.sql):", ", ".join(missing_tables))
    if missing_cols:
        print("Missing columns (run db/06_migrations.sql):", ", ".join(missing_cols))
    if not missing_tables and not missing_cols:
        print("Schema is complete for this version of EcoCart.")
    conn.close()


if __name__ == "__main__":
    main()
