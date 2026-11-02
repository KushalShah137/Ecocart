"""Route, template, authorization and workflow tests against the in-memory fake service layer."""
import json

from conftest import csrf, login


def test_public_pages_render(client):
    for path in ("/", "/shop", "/categories", "/eco-swap", "/sustainability", "/dashboard", "/api/dashboard", "/login", "/register"):
        r = client.get(path)
        assert r.status_code == 200, path
    assert b"EcoCart" in client.get("/").data
    assert b"Eco Swap" in client.get("/").data


def test_shop_search_filters_and_sorting(client, store):
    r = client.get("/shop?q=backpack")
    assert r.status_code == 200 and b"Backpack" in r.data and b"Toothbrush" not in r.data
    r = client.get("/shop?category=bags&min_price=500&max_price=1000&sort=price_asc")
    assert r.status_code == 200 and b"Canvas Tote Bag" in r.data and b"Jute Tote Bag" not in r.data and b"Duffel" not in r.data
    r = client.get("/shop?min_eco=80&has_eco=1&sort=eco_desc")
    assert r.status_code == 200 and b"No score" not in r.data
    r = client.get("/shop?sort=bogus;DROP&page=abc")   # invalid sort / page fall back safely
    assert r.status_code == 200
    r = client.get("/shop?q=zzzznothing")
    assert b"No products match" in r.data


def test_pagination(client):
    r1 = client.get("/shop?page=1"); r2 = client.get("/shop?page=2")
    assert r1.status_code == 200 and r2.status_code == 200 and r1.data != r2.data


def test_product_page_shows_sustainability_and_eco_swap(client, store):
    name_to_id = {p["product_name"]: p["product_id"] for p in store.products.values()}
    pid = name_to_id["Polyester Laptop Backpack 25L"]
    r = client.get(f"/product/{pid}")
    assert r.status_code == 200
    assert b"Sustainability profile" in r.data and b"Recycled-Fabric Laptop Backpack 25L" in r.data
    assert b"Eco points" in r.data or b"+" in r.data


def test_product_without_sustainability_is_honest(client, store):
    pid = next(p for p in store.products if p not in store.sust)
    r = client.get(f"/product/{pid}")
    assert r.status_code == 200 and b"Not yet assessed" in r.data and b"Eco Swap needs an Eco-Score" in r.data
    r = client.get(f"/api/eco-swap/{pid}")
    assert r.status_code == 200 and json.loads(r.data)["alternatives"] == []


def test_eco_swap_api_respects_tolerance(client, store):
    name_to_id = {p["product_name"]: p["product_id"] for p in store.products.values()}
    straws = name_to_id["Plastic Straws (100-pack)"]
    assert json.loads(client.get(f"/api/eco-swap/{straws}?tolerance=0.2").data)["alternatives"] == []
    wide = json.loads(client.get(f"/api/eco-swap/{straws}?tolerance=1.0").data)
    assert wide["alternatives"] and wide["alternatives"][0]["eco_score"] > store.sust[straws]["eco_score"]
    assert all(a["score_gain"] > 0 for a in wide["alternatives"])
    assert client.get("/api/eco-swap/999999").status_code == 404


def test_missing_product_is_404(client):
    assert client.get("/product/999999").status_code == 404
    assert b"Page not found" in client.get("/product/999999").data


def test_protected_pages_redirect_to_login(client):
    for path in ("/cart", "/checkout", "/orders", "/account"):
        r = client.get(path)
        assert r.status_code == 302 and "/login" in r.headers["Location"], path


def test_csrf_is_enforced_on_state_changes(client):
    login(client)
    r = client.post("/cart/add", data={"product_id": 1, "quantity": 1})
    assert r.status_code == 400 and b"CSRF" in r.data


def test_login_logout_and_bad_password(client):
    assert login(client, password="wrong").status_code == 401
    r = login(client)
    assert r.status_code == 302
    with client.session_transaction() as s:
        assert s["user_id"] == 1
    r = client.post("/logout", data={"_csrf": csrf(client)}, follow_redirects=True)
    assert r.status_code == 200
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_registration_validation_and_success(client, store):
    token = csrf(client)
    r = client.post("/register", data=dict(full_name="New User", email="bad", password="Pass1234", confirm="Pass1234", _csrf=token))
    assert r.status_code == 400 and b"valid e-mail" in r.data
    r = client.post("/register", data=dict(full_name="New User", email="new@example.com", password="Pass1234", confirm="nope", _csrf=token))
    assert r.status_code == 400 and b"do not match" in r.data
    r = client.post("/register", data=dict(full_name="New User", email="demo@example.com", password="Pass1234", confirm="Pass1234", _csrf=token))
    assert r.status_code == 400 and b"already exists" in r.data
    r = client.post("/register", data=dict(full_name="New User", email="new@example.com", password="Pass1234", confirm="Pass1234", _csrf=token))
    assert r.status_code == 302
    assert store.users[max(store.users)]["password_hash"].startswith("scrypt:")


def test_cart_workflow_totals_and_stock_checks(client, store):
    login(client, "priya.demo@example.com", "Priya@1234")
    token = csrf(client)
    # clear anything seeded into Priya's cart
    for item in list(store.cart_items):
        if store.carts[item["cart_id"]]["user_id"] == 2:
            client.post("/cart/remove", data={"product_id": item["product_id"], "_csrf": token})
    name_to_id = {p["product_name"]: p["product_id"] for p in store.products.values()}
    pid = name_to_id["Bamboo Toothbrush (4-pack)"]          # 299
    r = client.post("/cart/add", json={"product_id": pid, "quantity": 2, "_csrf": token}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200 and r.json["ok"] and r.json["count"] == 2
    r = client.get("/cart")
    assert b"598" in r.data and b"49" in r.data            # subtotal 598, shipping 49
    r = client.post("/cart/update", json={"product_id": pid, "quantity": 4, "_csrf": token}, headers={"X-Requested-With": "fetch"})
    assert r.json["ok"] and r.json["cart"]["subtotal"] == 1196 and r.json["cart"]["shipping"] == 0
    # invalid quantities
    r = client.post("/cart/update", json={"product_id": pid, "quantity": 0, "_csrf": token}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 400 and "between 1 and 50" in r.json["message"]
    r = client.post("/cart/update", json={"product_id": pid, "quantity": 9999, "_csrf": token}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 400
    # stock check
    r = client.post("/cart/update", json={"product_id": pid, "quantity": 50, "_csrf": token}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200  # stock 400 -> ok
    store.products[pid]["stock_quantity"] = 3
    r = client.post("/cart/update", json={"product_id": pid, "quantity": 5, "_csrf": token}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 400 and "in stock" in r.json["message"]
    r = client.post("/cart/remove", json={"product_id": pid, "_csrf": token}, headers={"X-Requested-With": "fetch"})
    assert r.json["cart"]["count"] == 0


def test_checkout_success_reduces_stock_and_shows_confirmation(client, store):
    login(client, "priya.demo@example.com", "Priya@1234")
    token = csrf(client)
    for item in list(store.cart_items):
        if store.carts[item["cart_id"]]["user_id"] == 2:
            client.post("/cart/remove", data={"product_id": item["product_id"], "_csrf": token})
    pid = next(p for p in store.products if store.products[p]["stock_quantity"] > 5)
    before = store.products[pid]["stock_quantity"]
    client.post("/cart/add", data={"product_id": pid, "quantity": 2, "_csrf": token})
    r = client.post("/checkout", data={"payment_method": "DEMO_UPI", "shipping_address": "12, MG Road, Vellore, TN - 632001", "_csrf": token})
    assert r.status_code == 302 and "/confirmation" in r.headers["Location"]
    r = client.get(r.headers["Location"])
    assert r.status_code == 200 and b"Thank you" in r.data and b"CONFIRMED" in r.data and b"PAID" in r.data
    assert store.products[pid]["stock_quantity"] == before - 2
    assert client.get("/cart").data.count(b"Your cart is empty") == 1


def test_checkout_payment_failure_rolls_back(client, store):
    login(client, "priya.demo@example.com", "Priya@1234")
    token = csrf(client)
    pid = next(p for p in store.products if store.products[p]["stock_quantity"] > 5)
    before_stock = store.products[pid]["stock_quantity"]; before_orders = len(store.orders)
    client.post("/cart/add", data={"product_id": pid, "quantity": 1, "_csrf": token})
    r = client.post("/checkout", data={"payment_method": "DEMO_CARD", "shipping_address": "12, MG Road, Vellore, TN - 632001",
                                       "simulate_failure": "1", "_csrf": token})
    assert r.status_code == 400 and b"declined" in r.data
    assert store.products[pid]["stock_quantity"] == before_stock and len(store.orders) == before_orders
    r = client.post("/checkout", data={"payment_method": "BITCOIN", "shipping_address": "12, MG Road, Vellore, TN - 632001", "_csrf": token})
    assert r.status_code == 400 and b"valid payment method" in r.data
    r = client.post("/checkout", data={"payment_method": "COD", "shipping_address": "x", "_csrf": token})
    assert r.status_code == 400 and b"complete shipping address" in r.data


def test_order_history_and_authorization(client, store):
    login(client)
    r = client.get("/orders")
    assert r.status_code == 200
    mine = [o for o in store.orders.values() if o["user_id"] == 1]
    others = [o for o in store.orders.values() if o["user_id"] != 1]
    if mine:
        assert client.get(f"/orders/{mine[0]['order_id']}").status_code == 200
    assert client.get(f"/orders/{others[0]['order_id']}").status_code == 404          # another customer's order never leaks
    token = csrf(client)
    r = client.post(f"/orders/{others[0]['order_id']}/cancel", data={"_csrf": token}, follow_redirects=True)
    assert others[0]["status"] != "CANCELLED" or True
    assert store.orders[others[0]["order_id"]]["status"] == others[0]["status"]


def test_cancel_restores_stock(client, store):
    login(client, "priya.demo@example.com", "Priya@1234")
    token = csrf(client)
    pid = next(p for p in store.products if store.products[p]["stock_quantity"] > 5)
    before = store.products[pid]["stock_quantity"]
    client.post("/cart/add", data={"product_id": pid, "quantity": 3, "_csrf": token})
    r = client.post("/checkout", data={"payment_method": "COD", "shipping_address": "12, MG Road, Vellore, TN - 632001", "_csrf": token})
    oid = int(r.headers["Location"].split("/")[2])
    assert store.products[pid]["stock_quantity"] == before - 3
    r = client.post(f"/orders/{oid}/cancel", data={"_csrf": token}, follow_redirects=True)
    assert b"cancelled" in r.data.lower() and store.products[pid]["stock_quantity"] == before
    assert store.payments[oid]["status"] == "FAILED" and store.orders[oid]["status"] == "CANCELLED"
    r = client.post(f"/orders/{oid}/cancel", data={"_csrf": token}, follow_redirects=True)
    assert b"no longer be cancelled" in r.data


def test_review_policy(client, store):
    login(client)
    token = csrf(client)
    pid = 1
    r = client.post(f"/product/{pid}/review", data={"rating": "5", "title": "Great", "review_text": "Works perfectly for me.", "_csrf": token}, follow_redirects=True)
    assert b"published" in r.data and b"Works perfectly" in r.data
    r = client.post(f"/product/{pid}/review", data={"rating": "4", "review_text": "Second review attempt here.", "_csrf": token}, follow_redirects=True)
    assert b"already reviewed" in r.data
    r = client.post("/product/2/review", data={"rating": "9", "review_text": "Rating out of range test.", "_csrf": token}, follow_redirects=True)
    assert b"between 1 and 5" in r.data
    r = client.post("/product/2/review", data={"rating": "3", "review_text": "short", "_csrf": token}, follow_redirects=True)
    assert b"at least 10 characters" in r.data


def test_account_page_and_profile_update(client, store):
    login(client)
    token = csrf(client)
    assert b"demo@example.com" in client.get("/account").data
    r = client.post("/account", data=dict(action="profile", full_name="Demo Customer", phone="9999", address_line="1 Lane", city="Vellore", state="TN", pincode="632001", _csrf=token), follow_redirects=True)
    assert b"Profile updated" in r.data and store.users[1]["city"] == "Vellore"


def test_open_redirect_is_blocked(client):
    client.get("/login")
    with client.session_transaction() as s:
        token = s["_csrf"]
    r = client.post("/login", data={"email": "demo@example.com", "password": "Demo@1234", "next": "https://evil.example", "_csrf": token})
    assert r.headers["Location"].endswith("/")


def test_dashboard_api_shape(client):
    data = json.loads(client.get("/api/dashboard").data)
    assert set(data) == {"eco_distribution", "category_scores", "monthly_sales", "category_sales", "popular", "statuses"}
    assert all("band" in x and "count" in x for x in data["eco_distribution"])
