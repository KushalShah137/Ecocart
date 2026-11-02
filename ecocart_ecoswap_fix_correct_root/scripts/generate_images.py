#!/usr/bin/env python3
"""
Generates one local SVG illustration per seeded product under
ecocart/static/img/products/p-<id>.svg, plus placeholder.svg.

Why local SVGs: the brief requires images that never break and never
misrepresent a product. Rather than borrowing photos of other products, each
card gets a clean category icon, the product's initials and brand colour.
Replace any file with a real product photo of the same name whenever you have one.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
from seed_data import generate  # noqa: E402
from catalog_data import CATEGORIES  # noqa: E402

OUT = os.path.join(ROOT, "ecocart", "static", "img", "products")

PALETTE = {  # per category: (background, accent)
    "electronics": ("#e8f1ec", "#1f6f4a"), "clothing": ("#f3efe6", "#8a5a2b"), "home-kitchen": ("#eaf0f4", "#2f5d7c"),
    "personal-care": ("#eef3e6", "#5a7d2a"), "bags": ("#f1ebe4", "#6b4e2e"), "stationery": ("#f4f0e8", "#b07a2a"),
    "reusables": ("#e6f2ef", "#17695b"), "lifestyle": ("#eef2e8", "#4c7a3a"),
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
    words = [w for w in name.replace("(", " ").replace(")", " ").replace("-", " ").split()
             if w[0].isalpha() and len(w) > 2]
    return "".join(w[0] for w in words[:2]).upper() or "ECO"


def svg(bg, accent, icon_path, text):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300" role="img" aria-label="{text} illustration">
<rect width="400" height="300" rx="20" fill="{bg}"/>
<circle cx="200" cy="130" r="86" fill="#ffffff" opacity="0.7"/>
<g transform="translate(150 80) scale(1)"><path d="{icon_path}" fill="none" stroke="{accent}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/></g>
<text x="200" y="262" text-anchor="middle" font-family="Inter, Helvetica, Arial, sans-serif" font-size="30" font-weight="700" fill="{accent}" letter-spacing="2">{text}</text>
</svg>
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    cat_by_id = {i: (slug, icon) for i, (_, slug, _, icon) in enumerate(CATEGORIES, start=1)}
    d = generate(lambda p: "x")
    for p in d.products:
        slug, icon = cat_by_id[p["category_id"]]
        bg, accent = PALETTE[slug]
        with open(os.path.join(OUT, f"p-{p['product_id']}.svg"), "w", encoding="utf-8") as f:
            f.write(svg(bg, accent, ICONS[icon], initials(p["product_name"])))
    with open(os.path.join(ROOT, "ecocart", "static", "img", "placeholder.svg"), "w", encoding="utf-8") as f:
        f.write(svg("#eef1ee", "#6b7b70", ICONS["leaf"], "ECO"))
    print(f"Wrote {len(d.products)} product images + placeholder.svg to {OUT}")


if __name__ == "__main__":
    main()
