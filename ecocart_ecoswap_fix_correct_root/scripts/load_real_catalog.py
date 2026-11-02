#!/usr/bin/env python3
"""Load the curated static real-world product catalogue into an existing EcoCart Oracle DB.

Run from the project root with the project's virtual environment active:
    python scripts/load_real_catalog.py

Updates existing product rows within each category (preserving IDs so existing
foreign keys remain valid), deactivates extra old catalogue rows, and rebuilds
illustrative sustainability estimates. This does not fetch live prices or stock.
"""
import os
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from catalog_data import CATEGORIES, MATERIALS, PACKAGING, PRODUCTS  # noqa: E402
from ecocart.db import get_connection  # noqa: E402
from ecocart.eco_methodology import compute_eco_score, METHODOLOGY_VERSION  # noqa: E402

PALETTE = {
    "electronics": ("#e8f1ec", "#1f6f4a", "bolt"), "clothing": ("#f3efe6", "#8a5a2b", "shirt"),
    "home-kitchen": ("#eaf0f4", "#2f5d7c", "home"), "personal-care": ("#eef3e6", "#5a7d2a", "leaf"),
    "bags": ("#f1ebe4", "#6b4e2e", "bag"), "stationery": ("#f4f0e8", "#b07a2a", "pen"),
    "reusables": ("#e6f2ef", "#17695b", "cup"), "lifestyle": ("#eef2e8", "#4c7a3a", "sprout"),
}
ICONS = {
    "bolt": "M52 10 L28 56 H48 L40 90 L72 40 H52 Z",
    "shirt": "M30 14 L48 8 Q50 18 52 8 L70 14 L88 30 L74 42 L74 92 H26 V42 L12 30 Z",
    "home": "M50 10 L92 46 H80 V90 H58 V64 H42 V90 H20 V46 H8 Z",
    "leaf": "M84 16 C40 16 18 44 18 84 C58 84 86 62 84 16 Z M22 82 L70 30",
    "bag": "M24 36 H76 L82 92 H18 Z M36 36 V28 A14 14 0 0 1 64 28 V36",
    "pen": "M18 82 L66 34 L80 48 L32 96 L14 100 Z M62 24 L76 10 L90 24 L76 38 Z",
    "cup": "M24 22 H70 L66 90 H28 Z M70 36 H82 A10 12 0 0 1 70 60",
    "sprout": "M50 92 V50 M50 60 C50 36 32 30 16 32 C18 50 30 62 50 60 Z M50 50 C50 30 66 22 84 24 C82 42 70 54 50 50 Z",
}

def initials(name):
    words = [w for w in name.replace("(", " ").replace(")", " ").replace("-", " ").split() if w and w[0].isalpha() and len(w) > 2]
    return "".join(w[0] for w in words[:2]).upper() or "ECO"

def make_svg(slug, name):
    bg, accent, icon = PALETTE[slug]
    label = initials(name).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300" role="img" aria-label="{label} category illustration"><rect width="400" height="300" rx="20" fill="{bg}"/><circle cx="200" cy="130" r="86" fill="#ffffff" opacity="0.7"/><g transform="translate(150 80)"><path d="{ICONS[icon]}" fill="none" stroke="{accent}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/></g><text x="200" y="262" text-anchor="middle" font-family="Inter, Helvetica, Arial, sans-serif" font-size="30" font-weight="700" fill="{accent}" letter-spacing="2">{label}</text></svg>'''

def main():
    conn = get_connection()
    cur = conn.cursor()
    image_dir = os.path.join(ROOT, "ecocart", "static", "img", "products")
    os.makedirs(image_dir, exist_ok=True)
    updated = 0
    deactivated = 0
    sustainability_rows = 0
    try:
        for _, slug, _, _ in CATEGORIES:
            cur.execute("SELECT category_id FROM category WHERE slug = :s", s=slug)
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"Category '{slug}' is missing. Run scripts/init_db.py first.")
            category_id = row[0]
            cur.execute("SELECT product_id FROM product WHERE category_id = :c ORDER BY product_id", c=category_id)
            existing_ids = [r[0] for r in cur.fetchall()]
            items = PRODUCTS[slug]
            if len(existing_ids) < len(items):
                raise RuntimeError(f"Category '{slug}' has only {len(existing_ids)} product rows; need {len(items)}. Run scripts/init_db.py first.")
            active_ids = existing_ids[:len(items)]
            extra_ids = existing_ids[len(items):]
            for product_id in extra_ids:
                cur.execute("UPDATE product SET is_active = 0 WHERE product_id = :p", p=product_id)
                cur.execute("DELETE FROM product_sustainability WHERE product_id = :p", p=product_id)
                deactivated += cur.rowcount
            for product_id, item in zip(active_ids, items):
                name, brand, price, mat, pkg, recyc, dur, stock, description, extra = item
                featured = 1 if (extra.get("featured") or name == items[0][0]) else 0
                cur.execute("""UPDATE product SET product_name=:n, brand=:b, description=:d, price=:pr,
                    stock_quantity=:st, image_url=:im, is_active=1, is_featured=:ft,
                    data_origin='ORIGINAL', source_key=:sk
                    WHERE product_id=:pid""",
                    n=name[:160], b=brand[:80], d=description[:1000], pr=Decimal(str(price)), st=stock,
                    im=f"/static/img/products/p-{product_id}.svg", ft=featured,
                    sk=f"CURATED-{slug}-{product_id}", pid=product_id)
                with open(os.path.join(image_dir, f"p-{product_id}.svg"), "w", encoding="utf-8") as f:
                    f.write(make_svg(slug, name))
                cur.execute("DELETE FROM product_sustainability WHERE product_id=:p", p=product_id)
                if mat is not None and pkg is not None:
                    mat_label, mat_score = MATERIALS[mat]
                    pkg_label, pkg_score = PACKAGING[pkg]
                    score = compute_eco_score(mat_score, pkg_score, recyc, dur)
                    cur.execute("""INSERT INTO product_sustainability
                        (product_id, material, packaging_type, recyclability_pct, eco_score,
                         carbon_footprint_kg, carbon_footprint_unit, sustainability_explanation,
                         score_source, data_origin)
                        VALUES (:pid,:mat,:pkg,:rec,:score,NULL,NULL,:expl,:src,'SYNTHETIC')""",
                        pid=product_id, mat=mat_label, pkg=pkg_label, rec=recyc, score=score,
                        expl=(f"Illustrative estimate based on assumed material, packaging, recyclability and durability inputs. Not a verified assessment."),
                        src=(f"{METHODOLOGY_VERSION}; assumed inputs; illustrative, not verified")[:200])
                    sustainability_rows += 1
                updated += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    print(f"Catalogue loaded successfully: {updated} products updated; {deactivated} old rows deactivated; {sustainability_rows} illustrative Eco-Scores rebuilt.")
    print("Prices and stock are static demo values. Product images are local category illustrations, not product photographs.")

if __name__ == "__main__":
    main()
