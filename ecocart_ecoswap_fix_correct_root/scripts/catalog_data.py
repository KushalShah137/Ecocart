"""
EcoCart static product catalogue.

Product names and brands are real-world examples. Prices and stock are illustrative
static demo values, not live or verified current retailer data. Sustainability inputs
are educational estimates, not product-specific verified environmental measurements.

Product tuple layout:
  (name, brand, price_inr, material_key, packaging_key, recyclability_pct,
   durability_score, stock, description, extra)
  material_key = None  -> product is deliberately left WITHOUT sustainability data
  extra: optional dict  {"carbon": kg_co2e_estimate, "featured": True}
"""

CATEGORIES = [
    # (name, slug, description, icon)
    ("Electronics & Accessories", "electronics",
     "Chargers, audio, lighting and everyday gadgets with energy-efficiency ratings.", "bolt"),
    ("Clothing & Apparel", "clothing",
     "T-shirts, kurtas and everyday wear in organic and conventional fabrics.", "shirt"),
    ("Home & Kitchen", "home-kitchen",
     "Cookware, storage and tableware for a lower-impact kitchen.", "home"),
    ("Personal Care", "personal-care",
     "Toothbrushes, soaps and grooming essentials.", "leaf"),
    ("Bags & Accessories", "bags",
     "Backpacks, totes, wallets and belts.", "bag"),
    ("Stationery", "stationery",
     "Notebooks, pens and desk supplies for school and office.", "pen"),
    ("Reusable Essentials", "reusables",
     "Bottles, cups, straws and food wraps that replace single-use items.", "cup"),
    ("Sustainable Lifestyle", "lifestyle",
     "Composting, gardening and home products for a greener routine.", "sprout"),
]

# ---------------------------------------------------------------------------
# Material classes used by the scoring methodology (score 0-100 = assumed
# relative impact of raw material; higher is better).
# ---------------------------------------------------------------------------
MATERIALS = {
    "rpet":            ("Recycled PET fabric (rPET)", 85),
    "organic_cotton":  ("Organic cotton", 80),
    "cotton":          ("Conventional cotton", 50),
    "polyester":       ("Virgin polyester", 30),
    "nylon":           ("Nylon", 28),
    "stainless":       ("Food-grade stainless steel (304)", 75),
    "glass":           ("Borosilicate glass", 70),
    "bamboo":          ("Bamboo", 88),
    "plastic":         ("Virgin plastic (PP/PET)", 25),
    "rplastic":        ("Recycled plastic (rHDPE/rPP)", 70),
    "jute":            ("Natural jute", 90),
    "rpaper":          ("100% recycled paper", 85),
    "paper":           ("Virgin wood-pulp paper", 45),
    "aluminium":       ("Aluminium", 60),
    "electronics":     ("Mixed electronics (PCB, ABS housing)", 20),
    "electronics_r":   ("Recycled ABS housing with standard electronics", 40),
    "wood":            ("FSC-certified wood", 80),
    "silicone":        ("Food-grade silicone", 55),
    "coconut":         ("Coconut coir / shell", 92),
    "linen":           ("Linen (flax)", 78),
    "wool":            ("Wool blend", 60),
    "leather":         ("Leather", 35),
    "cork":            ("Cork", 90),
    "steel":           ("Powder-coated steel", 60),
    "ceramic":         ("Ceramic", 55),
    "terracotta":      ("Terracotta clay", 85),
    "hemp":            ("Hemp fabric", 86),
    "cotton_blend":    ("Cotton-polyester blend", 40),
}

PACKAGING = {
    "none":        ("No packaging / loose", 100),
    "kraft":       ("Minimal recycled kraft paper", 90),
    "cloth":       ("Reusable cloth pouch", 88),
    "sleeve":      ("Paper sleeve", 85),
    "cardboard":   ("Recyclable cardboard box", 75),
    "mixed":       ("Mixed plastic and cardboard", 40),
    "bubble":      ("Bubble wrap in cardboard", 35),
    "polybag":     ("Single-use plastic polybag", 20),
    "blister":     ("Plastic blister pack", 10),
}

# Curated real-world product names and brands for a static educational catalogue.
# Prices are illustrative static values, not verified current retailer prices.
B = {}

PRODUCTS = {
"electronics": [
    ('Philips 9W LED Bulb B22', 'Philips', 149, 'electronics', 'cardboard', 25, 80, 80, 'LED bulb for everyday home lighting; price is a static catalogue estimate.', {}),
    ('Syska 12W LED Bulb B22', 'Syska', 129, 'electronics', 'cardboard', 25, 75, 70, '12W LED bulb for household lighting; price is a static catalogue estimate.', {}),
    ('Mi Power Bank 3i 10000mAh', 'Xiaomi', 1499, 'electronics', 'cardboard', 20, 75, 35, 'Portable 10000mAh power bank; verify variant and current price at the retailer.', {}),
    ('boAt Stone 350 Bluetooth Speaker', 'boAt', 1499, 'electronics', 'cardboard', 20, 65, 25, 'Portable Bluetooth speaker; specifications can vary by model.', {}),
    ('Portronics Konnect L USB Cable', 'Portronics', 199, 'plastic', 'polybag', 10, 55, 100, 'USB charging cable; connector and length depend on selected variant.', {}),
    ('Samsung 25W USB-C Power Adapter', 'Samsung', 1299, 'electronics', 'cardboard', 20, 80, 30, 'USB-C fast-charging adapter; check device compatibility.', {}),
    ('Duracell Rechargeable AA Batteries 4-Pack', 'Duracell', 799, 'electronics', 'cardboard', 35, 85, 40, 'Rechargeable AA battery pack; capacity depends on the specific pack.', {}),
    ('TP-Link Tapo P110 Smart Plug', 'TP-Link', 1199, 'electronics', 'cardboard', 20, 75, 20, 'Wi-Fi smart plug with energy-monitoring features on supported versions.', {}),
    ('Philips 12W LED Bulb B22', 'Philips', 179, 'electronics', 'cardboard', 25, 80, 70, '12W household LED bulb; price is a static catalogue estimate.', {}),
    ('boAt Airdopes 141 Earbuds', 'boAt', 1299, 'electronics', 'cardboard', 15, 55, 25, 'Wireless earbuds; exact features vary by variant.', {}),
    ('Logitech B100 USB Mouse', 'Logitech', 299, 'plastic', 'cardboard', 10, 65, 35, 'Wired USB mouse for desktop use.', {}),
    ('HP 150 Wireless Keyboard and Mouse Combo', 'HP', 1499, 'plastic', 'cardboard', 10, 65, 20, 'Wireless keyboard-and-mouse set; confirm layout and included receiver.', {}),
    ('SanDisk Ultra USB 3.0 Flash Drive 64GB', 'SanDisk', 599, None, None, None, None, 30, 'USB flash drive; capacity and interface depend on variant.', {}),
],
"clothing": [
    ("Levi's Men Solid Crew-Neck T-Shirt", "Levi's", 699, 'cotton', 'polybag', 40, 65, 45, 'Everyday crew-neck T-shirt; colour and fabric blend vary by listing.', {}),
    ('Jockey Cotton Rich Round-Neck T-Shirt', 'Jockey', 599, 'cotton_blend', 'polybag', 35, 70, 45, 'Round-neck T-shirt; check the product listing for exact fabric composition.', {}),
    ('Max Men Solid Regular-Fit T-Shirt', 'Max Fashion', 399, 'cotton', 'polybag', 40, 55, 55, 'Basic regular-fit T-shirt; price varies by colour and size.', {}),
    ('Allen Solly Men Polo T-Shirt', 'Allen Solly', 999, 'cotton', 'polybag', 40, 70, 30, 'Polo T-shirt; confirm material and fit for the selected variant.', {}),
    ('Fabindia Cotton Kurta', 'Fabindia', 1499, 'cotton', 'kraft', 45, 70, 25, 'Cotton kurta; product patterns and fabric may vary by collection.', {}),
    ('Decathlon Kipsta Sports T-Shirt', 'Decathlon', 499, 'polyester', 'polybag', 20, 60, 40, 'Sports T-shirt; check the listing for the exact fabric and model.', {}),
    ('Biba Printed Straight Kurta', 'Biba', 1299, 'cotton_blend', 'polybag', 35, 65, 25, 'Printed straight kurta; material and price depend on the selected design.', {}),
    ('Bewakoof Graphic Printed T-Shirt', 'Bewakoof', 499, 'cotton', 'polybag', 40, 55, 45, 'Graphic T-shirt; artwork and colour vary by listing.', {}),
    ('Jockey Men Cotton Vest 2-Pack', 'Jockey', 499, 'cotton', 'polybag', 40, 65, 35, 'Packaged cotton vests; check size and fabric composition.', {}),
    ('Decathlon Domyos Training Shorts', 'Decathlon', 599, 'polyester', 'polybag', 20, 60, 35, 'Training shorts; fabric and fit vary by model.', {}),
    ('Van Heusen Men Formal Shirt', 'Van Heusen', 1499, 'cotton_blend', 'polybag', 35, 65, 20, 'Formal shirt; composition depends on the selected variant.', {}),
    ('Puma Essentials Logo T-Shirt', 'Puma', 999, 'cotton', 'polybag', 40, 65, 25, 'Logo T-shirt; colour and composition vary by listing.', {}),
    ('Manyavar Cotton Blend Kurta', 'Manyavar', 1999, None, None, None, None, 15, 'Kurta listing; confirm exact fabric composition on the retailer page.', {}),
],
"home-kitchen": [
    ('Milton Steel Lunch Box', 'Milton', 599, 'stainless', 'cardboard', 80, 90, 35, 'Reusable lunch box; confirm capacity and compartment count for the variant.', {}),
    ('Borosil Glass Storage Container', 'Borosil', 499, 'glass', 'cardboard', 75, 80, 30, 'Glass food-storage container; lid material varies by model.', {}),
    ('Prestige Popular Aluminium Pressure Cooker', 'Prestige', 1699, 'aluminium', 'cardboard', 55, 85, 20, 'Aluminium pressure cooker; select capacity and model carefully.', {}),
    ('Hawkins Contura Pressure Cooker', 'Hawkins', 2199, 'aluminium', 'cardboard', 55, 90, 18, 'Pressure cooker available in multiple capacities.', {}),
    ('Cello Swift Stainless Steel Lunch Box', 'Cello', 499, 'stainless', 'cardboard', 80, 80, 35, 'Stainless-steel lunch box; check dimensions and compartments.', {}),
    ('Tupperware Modular Mate Storage Container', 'Tupperware', 399, 'plastic', 'cardboard', 20, 75, 35, 'Reusable food-storage container; size and lid style vary by model.', {}),
    ('Pigeon Non-Stick Tawa', 'Pigeon', 499, 'aluminium', 'cardboard', 30, 55, 30, 'Non-stick tawa; coating and diameter vary by model.', {}),
    ('IKEA 365+ Food Container', 'IKEA', 299, 'glass', 'cardboard', 70, 75, 25, 'Reusable food container; check whether the chosen variant is glass or plastic.', {}),
    ('Milton Thermosteel Flask 1L', 'Milton', 1299, 'stainless', 'cardboard', 80, 85, 20, 'Insulated flask; capacity and lid design depend on model.', {}),
    ('Prestige Omega Select Plus Fry Pan', 'Prestige', 999, 'aluminium', 'cardboard', 30, 65, 25, 'Fry pan; coating and diameter vary by variant.', {}),
    ('Borosil Vision Glass Mixing Bowl', 'Borosil', 399, 'glass', 'cardboard', 75, 75, 25, 'Glass mixing bowl; size varies by listing.', {}),
    ('Cello Opalware Dinner Set', 'Cello', 1999, 'ceramic', 'cardboard', 50, 70, 15, 'Dinner set; piece count and pattern vary.', {}),
    ('IKEA KORKEN Jar with Lid', 'IKEA', 199, 'glass', 'cardboard', 75, 75, 30, 'Glass jar with lid; size and lid material vary.', {}),
],
"personal-care": [
    ('Colgate Strong Teeth Toothpaste 200g', 'Colgate', 120, 'plastic', 'mixed', 20, 45, 80, 'Packaged toothpaste; pack size and formulation may vary by listing.', {}),
    ('Dove Cream Beauty Bathing Bar 3-Pack', 'Dove', 180, 'plastic', 'mixed', 20, 50, 60, 'Pack of bathing bars; packaging and pack size vary.', {}),
    ('Himalaya Purifying Neem Face Wash', 'Himalaya', 175, 'plastic', 'mixed', 20, 50, 50, 'Neem face wash; check the listing for exact size and ingredients.', {}),
    ('Pears Pure and Gentle Soap 3-Pack', 'Pears', 165, 'plastic', 'mixed', 20, 50, 55, 'Packaged bathing soap; pack size may vary.', {}),
    ('Dettol Original Bathing Soap 4-Pack', 'Dettol', 190, 'plastic', 'mixed', 20, 50, 55, 'Pack of bathing soaps; exact pack size depends on the listing.', {}),
    ('Nivea Soft Moisturising Cream', 'Nivea', 249, 'plastic', 'mixed', 20, 50, 40, 'Moisturising cream; jar size varies by variant.', {}),
    ('Oral-B Cross Action Toothbrush', 'Oral-B', 149, 'plastic', 'blister', 10, 45, 60, 'Manual toothbrush; head and bristle design vary by model.', {}),
    ('Mamaearth Onion Shampoo', 'Mamaearth', 349, 'plastic', 'mixed', 20, 45, 35, 'Packaged shampoo; check bottle size and formula on the listing.', {}),
    ('Sensodyne Fresh Mint Toothpaste', 'Sensodyne', 160, 'plastic', 'mixed', 20, 45, 45, 'Packaged toothpaste; tube size and formulation vary.', {}),
    ('Gillette Mach3 Razor', 'Gillette', 299, 'plastic', 'blister', 10, 50, 35, 'Manual razor; included cartridge count varies.', {}),
    ('Head & Shoulders Anti-Dandruff Shampoo', 'Head & Shoulders', 299, 'plastic', 'mixed', 20, 45, 35, 'Packaged shampoo; bottle size and formula vary.', {}),
    ('Patanjali Aloe Vera Gel', 'Patanjali', 100, 'plastic', 'mixed', 20, 40, 40, 'Packaged aloe vera gel; check ingredients and pack size.', {}),
    ('The Body Shop Shea Body Butter', 'The Body Shop', 1095, None, None, None, None, 15, 'Moisturising body butter; verify the selected product size.', {}),
],
"bags": [
    ('Wildcraft 45L Trekking Backpack', 'Wildcraft', 2999, 'nylon', 'polybag', 20, 75, 15, 'Trekking backpack; capacity and pocket layout depend on model.', {}),
    ('Skybags Brat Backpack', 'Skybags', 1199, 'polyester', 'polybag', 20, 60, 25, 'Everyday backpack; colour and capacity vary by listing.', {}),
    ('Safari Thorium Hard-Sided Trolley Bag', 'Safari', 3499, 'plastic', 'polybag', 20, 75, 15, 'Hard-sided luggage; wheel and size configuration varies.', {}),
    ('American Tourister Casual Backpack', 'American Tourister', 1999, 'polyester', 'polybag', 20, 70, 20, 'Casual backpack; confirm capacity and model.', {}),
    ('Decathlon Quechua Hiking Backpack', 'Decathlon', 1499, 'polyester', 'polybag', 20, 70, 20, 'Hiking backpack; litres and features depend on model.', {}),
    ('Fastrack Wallet', 'Fastrack', 499, 'leather', 'kraft', 20, 55, 30, 'Wallet; verify whether the selected listing uses leather or a synthetic material.', {}),
    ('Mokobara The Transit Backpack', 'Mokobara', 5999, 'polyester', 'polybag', 20, 75, 10, 'Travel backpack; exact design and capacity depend on model.', {}),
    ('DailyObjects Tote Bag', 'DailyObjects', 999, 'cotton_blend', 'kraft', 35, 55, 20, 'Tote bag; material and print depend on the selected design.', {}),
    ('Safari Pentagon Laptop Backpack', 'Safari', 1799, 'polyester', 'polybag', 20, 65, 20, 'Laptop backpack; capacity and laptop sleeve size vary.', {}),
    ('Wildcraft Wiki 3 Backpack', 'Wildcraft', 999, 'polyester', 'polybag', 20, 60, 25, 'Everyday backpack; check volume and pocket layout.', {}),
    ('American Tourister Liftoff Trolley Bag', 'American Tourister', 4999, 'plastic', 'polybag', 20, 75, 12, 'Trolley luggage; size and shell material vary by model.', {}),
    ('Decathlon Quechua Hiking Waist Bag', 'Decathlon', 499, 'polyester', 'polybag', 20, 60, 25, 'Compact hiking waist bag; dimensions vary by model.', {}),
    ('Fastrack Sling Bag', 'Fastrack', 999, None, None, None, None, 20, 'Sling bag; material and dimensions depend on selected variant.', {}),
],
"stationery": [
    ('Classmate Single-Line Notebook  long book', 'Classmate', 60, 'paper', 'sleeve', 45, 45, 100, 'Paper notebook; page count and ruling vary by variant.', {}),
    ('Reynolds 045 Ball Pen Pack', 'Reynolds', 100, 'plastic', 'blister', 10, 35, 80, 'Ball pens; pack count and ink colour vary.', {}),
    ('Cello Butterflow Ball Pen Pack', 'Cello', 100, 'plastic', 'blister', 10, 35, 80, 'Ball pens; confirm pack count and ink colour.', {}),
    ('Faber-Castell Connector Pen Set', 'Faber-Castell', 199, 'plastic', 'cardboard', 15, 45, 45, 'Colouring pen set; number of pens depends on the pack.', {}),
    ('Camlin Kokuyo Geometry Box', 'Camlin Kokuyo', 99, 'plastic', 'cardboard', 15, 45, 50, 'Geometry set for school use; included instruments vary by version.', {}),
    ('Kokuyo Camlin Drawing Book', 'Kokuyo Camlin', 80, 'paper', 'sleeve', 45, 45, 60, 'Drawing book; size and paper count vary by listing.', {}),
    ('Pilot V5 Hi-Tecpoint Pen', 'Pilot', 80, 'plastic', 'blister', 10, 45, 45, 'Liquid-ink pen; tip size and ink colour vary.', {}),
    ('Scotch Magic Tape', 'Scotch', 149, 'plastic', 'cardboard', 10, 50, 40, 'Adhesive office tape; width and roll length vary.', {}),
    ('Classmate Practical Notebook', 'Classmate', 80, 'paper', 'sleeve', 45, 45, 60, 'School practical notebook; page count varies.', {}),
    ('Luxor Highlighter Set', 'Luxor', 120, 'plastic', 'blister', 10, 35, 40, 'Highlighter set; colour count varies by pack.', {}),
    ('Camlin Brush Pens Set', 'Camlin', 199, 'plastic', 'cardboard', 15, 45, 35, 'Brush pen set; number of colours depends on pack.', {}),
    ('Faber-Castell Triangular Colour Pencils', 'Faber-Castell', 199, 'wood', 'cardboard', 45, 50, 35, 'Colour pencil set; pencil count varies.', {}),
    ('Paperkraft Premium Notebook', 'Paperkraft', 150, None, None, None, None, 35, 'Paper notebook; page count and cover vary by listing.', {}),
],
"reusables": [
    ('Milton Thermosteel Water Bottle 750ml', 'Milton', 899, 'stainless', 'cardboard', 80, 85, 30, 'Reusable insulated bottle; capacity and lid design vary.', {}),
    ('Borosil Hydra Stainless Steel Bottle', 'Borosil', 699, 'stainless', 'cardboard', 80, 80, 30, 'Reusable bottle; confirm capacity for the chosen variant.', {}),
    ('Cello Puro Stainless Steel Bottle', 'Cello', 399, 'stainless', 'cardboard', 80, 75, 35, 'Reusable stainless-steel bottle; size varies by listing.', {}),
    ('Tupperware Eco Bottle', 'Tupperware', 499, 'plastic', 'cardboard', 20, 65, 25, 'Reusable bottle; check capacity and exact material.', {}),
    ('Nayasa Reusable Water Bottle', 'Nayasa', 199, 'plastic', 'polybag', 20, 45, 50, 'Reusable bottle; model and capacity vary.', {}),
    ('Bamboo Reusable Drinking Straws Set', 'Generic marketplace listing', 249, 'bamboo', 'kraft', 80, 50, 25, 'Reusable bamboo straw set; this is a generic listing type, not a single branded SKU.', {}),
    ('Stainless Steel Reusable Straw Set', 'Generic marketplace listing', 199, 'stainless', 'kraft', 80, 75, 25, 'Reusable steel straw set; this is a generic listing type, not a single branded SKU.', {}),
    ('Borosil Glass Water Bottle', 'Borosil', 499, 'glass', 'cardboard', 75, 65, 25, 'Reusable glass bottle; check protective sleeve and capacity.', {}),
    ('Milton Thermosteel Tumbler', 'Milton', 599, 'stainless', 'cardboard', 80, 80, 25, 'Reusable insulated tumbler; volume varies by model.', {}),
    ('Cello Insulated Travel Mug', 'Cello', 499, 'stainless', 'cardboard', 80, 75, 25, 'Reusable travel mug; lid design and volume vary.', {}),
    ('Borosil Glass Lunch Box', 'Borosil', 699, 'glass', 'cardboard', 75, 70, 20, 'Reusable glass lunch box; lid material varies.', {}),
    ('Tupperware Lunch Box', 'Tupperware', 599, 'plastic', 'cardboard', 20, 65, 25, 'Reusable lunch box; compartments and capacity vary.', {}),
    ('Milton Copper Bottle', 'Milton', 799, None, None, None, None, 20, 'Reusable bottle listing; verify material, capacity, and care instructions.', {}),
],
"lifestyle": [
    ('Ugaoo Indoor Plant Grow Kit', 'Ugaoo', 499, 'terracotta', 'cardboard', 60, 55, 25, 'Indoor gardening kit; contents depend on the selected kit.', {}),
    ('IKEA SOCKER Plant Pot', 'IKEA', 199, 'steel', 'cardboard', 60, 75, 25, 'Plant pot; size and finish vary by variant.', {}),
    ('TrustBasket Organic Vermicompost', 'TrustBasket', 299, 'paper', 'kraft', 70, 45, 30, 'Packaged vermicompost; bag size and composition vary.', {}),
    ('Ugaoo Money Plant', 'Ugaoo', 299, 'plastic', 'mixed', 20, 45, 25, 'Live houseplant listing; pot and plant size depend on the selected option.', {}),
    ('Neem Oil Garden Spray', 'Generic marketplace listing', 249, 'plastic', 'mixed', 20, 40, 25, 'Garden neem-oil product; concentration and volume must be checked on the listing.', {}),
    ('Home Composting Bin', 'Generic marketplace listing', 1499, 'plastic', 'cardboard', 25, 75, 12, 'Home composting bin; capacity and ventilation design vary.', {}),
    ('Kraft Paper Seedling Pots Set', 'Generic marketplace listing', 199, 'paper', 'kraft', 70, 30, 35, 'Seedling pot set; dimensions and count vary by listing.', {}),
    ('Cocopeat Grow Bag', 'TrustBasket', 249, 'coconut', 'kraft', 80, 45, 30, 'Cocopeat growing medium; pack size and blend vary.', {}),
    ('Ugaoo Succulent Plant', 'Ugaoo', 249, 'terracotta', 'cardboard', 60, 50, 20, 'Live succulent listing; plant and pot size vary.', {}),
    ('TrustBasket Cocopeat Block', 'TrustBasket', 199, 'coconut', 'kraft', 80, 45, 30, 'Cocopeat growing medium; weight and expansion vary by pack.', {}),
    ('IKEA FEJKA Artificial Plant', 'IKEA', 299, 'plastic', 'cardboard', 20, 65, 20, 'Artificial plant; size and pot style vary by listing.', {}),
    ('Ugaoo Garden Tool Set', 'Ugaoo', 499, 'steel', 'cardboard', 55, 65, 20, 'Home gardening tool set; tool count varies by kit.', {}),
    ('Compostable Garbage Bags', 'Generic marketplace listing', 299, None, None, None, None, 25, 'Generic compostable bag listing; certification and material claims require verification.', {}),
],
}

# Fictional customers (reserved example.com addresses only).
FIRST_NAMES = ["Aarav", "Ananya", "Vihaan", "Diya", "Arjun", "Isha", "Kabir", "Meera", "Rohan", "Sanya",
               "Aditya", "Nisha", "Karthik", "Pooja", "Rahul", "Sneha", "Vikram", "Tara", "Nikhil", "Kavya",
               "Siddharth", "Riya", "Manav", "Anjali", "Dev", "Shreya", "Harsh", "Ira", "Yash", "Lakshmi",
               "Abhinav", "Mitali", "Pranav", "Ritika", "Sahil", "Trisha", "Varun"]
LAST_NAMES = ["Sharma", "Iyer", "Patel", "Reddy", "Nair", "Mehta", "Khan", "Das", "Banerjee", "Joshi",
              "Kulkarni", "Menon", "Verma", "Rao", "Pillai", "Chauhan", "Gupta", "Bhat", "Mishra", "Sen"]
CITIES = [("Chennai", "Tamil Nadu", "600001"), ("Vellore", "Tamil Nadu", "632001"), ("Bengaluru", "Karnataka", "560001"),
          ("Hyderabad", "Telangana", "500001"), ("Mumbai", "Maharashtra", "400001"), ("Pune", "Maharashtra", "411001"),
          ("Delhi", "Delhi", "110001"), ("Kolkata", "West Bengal", "700001"), ("Kochi", "Kerala", "682001"),
          ("Jaipur", "Rajasthan", "302001"), ("Ahmedabad", "Gujarat", "380001"), ("Coimbatore", "Tamil Nadu", "641001")]
STREETS = ["MG Road", "Anna Salai", "Gandhi Nagar", "Nehru Street", "Lake View Colony", "Rose Garden Lane",
           "Station Road", "Temple Street", "Park Avenue", "Green Park"]


REVIEW_TEMPLATES = {
    5: [("Excellent quality", "Exactly as described. {name} feels premium and the packaging was minimal, which I appreciated."),
        ("Loved it", "Been using it for a month now and it still looks new. Would buy from {brand} again."),
        ("Worth every rupee", "Great build, quick delivery to {city}. The eco-score badge actually matched my expectations."),
        ("Perfect for daily use", "Switched from the conventional version and honestly cannot tell the difference, except this one is better made.")],
    4: [("Good product", "Does the job well. Slightly pricier than alternatives but the quality justifies it."),
        ("Happy with the purchase", "Nice finish and sturdy. Took a day longer to deliver than promised."),
        ("Recommended", "Good value from {brand}. Minor scuff on arrival but nothing serious.")],
    3: [("Average", "It is okay. Works as expected but nothing special about it."),
        ("Decent but not great", "Reasonable quality for the price. The description could be more detailed.")],
    2: [("Not as expected", "The size is smaller than it looks in the picture. Customer support was helpful though."),
        ("Below expectations", "Build quality is weaker than I hoped for {name}. Might not last long.")],
    1: [("Disappointed", "Arrived damaged and the replacement took two weeks. Would not recommend."),
        ("Poor quality", "Stopped working within a week. Returned it.")],
}
