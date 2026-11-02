"""Pure-logic tests: Eco-Score methodology, dataset consistency, security helpers, SQL splitter, SQL whitelists."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))

from ecocart.eco_methodology import compute_eco_score, eco_grade  # noqa: E402
from ecocart.security import hash_password, validate_email, validate_password, verify_password  # noqa: E402
from ecocart.services import catalog  # noqa: E402
from init_db import split_statements  # noqa: E402
from import_dataset import parse_date, parse_money, resolve  # noqa: E402
from seed_data import eco_swap_pairs, generate, validate  # noqa: E402


def test_eco_score_formula_and_bounds():
    assert compute_eco_score(100, 100, 100, 100) == 100
    assert compute_eco_score(0, 0, 0, 0) == 0
    # 0.4*85 + 0.25*90 + 0.2*45 + 0.15*85 = 34 + 22.5 + 9 + 12.75 = 78.25 -> 78
    assert compute_eco_score(85, 90, 45, 85) == 78
    # .5 rounds away from zero like Oracle ROUND(): 0.4*50+0.25*50+0.2*50+0.15*50 = 50
    assert compute_eco_score(50, 50, 50, 50) == 50
    assert compute_eco_score(None, 100, None, None) == 25


def test_grade_bands():
    assert eco_grade(None) == "N/A"
    assert eco_grade(80) == "A" and eco_grade(79) == "B"
    assert eco_grade(65) == "B" and eco_grade(50) == "C" and eco_grade(35) == "D" and eco_grade(0) == "E"


def test_generated_dataset_is_consistent_and_meets_targets():
    d = generate(lambda p: "hash")
    assert validate(d) == []
    assert len(d.categories) >= 8 and 100 <= len(d.products) <= 150
    assert 30 <= len(d.users) <= 50 and 60 <= len(d.orders) <= 100
    assert len(d.order_items) >= 100 and len(d.reviews) >= 50 and len(d.payments) == len(d.orders)
    assert 0 < len(d.products) - len(d.sustainability) <= 10          # some products deliberately unscored
    assert all(u["email"].endswith("@example.com") for u in d.users)
    assert all(u["data_origin"] == "SYNTHETIC" for u in d.users)


def test_generation_is_deterministic():
    a, b = generate(lambda p: "h"), generate(lambda p: "h")
    assert [o["order_ref"] for o in a.orders] == [o["order_ref"] for o in b.orders]
    assert [r["review_text"] for r in a.reviews] == [r["review_text"] for r in b.reviews]


def test_eco_swap_pairs_exist_for_the_brief_examples():
    d = generate(lambda p: "h")
    by_name = {p["product_name"]: p for p in d.products}
    pairs = eco_swap_pairs(d)
    poly_backpack = by_name["Polyester Laptop Backpack 25L"]["product_id"]
    rpet_backpack = by_name["Recycled-Fabric Laptop Backpack 25L"]["product_id"]
    assert rpet_backpack in pairs[poly_backpack]
    plastic_bottles = by_name["Plastic Water Bottle 1L (12-pack)"]["product_id"]
    steel_bottle = by_name["Stainless Steel Water Bottle 1L (insulated)"]["product_id"]
    assert steel_bottle in pairs[plastic_bottles]
    # an honest empty state: plastic straws at Rs 99 have no alternative within +/-20 %
    assert by_name["Plastic Straws (100-pack)"]["product_id"] not in pairs


def test_password_hashing_and_validation():
    h = hash_password("Demo@1234")
    assert h.startswith("scrypt:") and verify_password(h, "Demo@1234") and not verify_password(h, "wrong")
    assert validate_password("short1") and validate_password("longenoughbutnodigits") and validate_password("12345678")
    assert validate_password("Demo@1234") is None
    assert validate_email("not-an-email") and validate_email("a@b.co") is None


def test_sort_keys_are_whitelisted():
    assert "price_asc" in catalog.SORTS
    assert catalog.SORTS.get("1; DROP TABLE product") is None
    for frag in catalog.SORTS.values():
        assert ";" not in frag and "--" not in frag


def test_filters_build_bind_variables_only():
    where, binds = catalog._filters(q="x' OR 1=1 --", category="bags", min_price=10, max_eco=50, in_stock=True)
    assert "OR 1=1" not in where and ":q" in where and binds["q"] == "x' OR 1=1 --"
    assert where.count(":") == 4 and binds["cat"] == "bags"


def test_sql_splitter_handles_plsql_blocks():
    text = """
-- comment
SET DEFINE OFF
CREATE TABLE t (x NUMBER);
CREATE OR REPLACE FUNCTION f RETURN NUMBER IS
BEGIN
  RETURN 1;
END;
/
INSERT INTO t VALUES (1);
BEGIN
  NULL;
END;
/
"""
    stmts = split_statements(text)
    assert len(stmts) == 4
    assert stmts[0] == "CREATE TABLE t (x NUMBER)"
    assert stmts[1].startswith("CREATE OR REPLACE FUNCTION") and stmts[1].endswith("END;")
    assert stmts[2] == "INSERT INTO t VALUES (1)"


def test_every_sql_script_splits_cleanly():
    for f in os.listdir(os.path.join(ROOT, "db")):
        with open(os.path.join(ROOT, "db", f), encoding="utf-8") as fh:
            stmts = split_statements(fh.read())
        assert stmts, f
        for s in stmts:
            assert s.strip(), f


def test_importer_helpers():
    assert resolve(["Customer ID", "Name"], "customer_id", {}) == "Customer ID"
    assert resolve(["foo"], "customer_id", {"customer_id": "foo"}) == "foo"
    assert resolve(["foo"], "customer_id", {}) is None
    assert str(parse_money("₹1,299.50")) == "1299.50" and parse_money("abc") is None
    assert parse_date("12-03-2025").month == 3 and parse_date("2025-03-12").day == 12 and parse_date("nope") is None
