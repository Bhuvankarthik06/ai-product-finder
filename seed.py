"""Fills the database with sample products (fictional brands, INR prices).

Usage:  python seed.py          # add sample data if the table is empty
        python seed.py --reset  # drop and re-seed
"""
import random
import sys

from app import app
from models import Product, db
from recommender import recommender

random.seed(42)

CATALOG = {
    "Smartphones": {
        "brands": ["Zenvo", "Arcwave", "Pixelon", "Novatek", "Lumio"],
        "tiers": [
            ("Lite", 9999, 14999, "6.5-inch display, 5000mAh battery, 50MP dual camera", "Everyday phone with long battery life and a dependable camera for daily use."),
            ("Neo", 15999, 24999, "6.7-inch AMOLED, 5000mAh battery, 64MP camera with OIS, 33W fast charging", "Sharp AMOLED screen and a stabilised camera that handles low-light photos well."),
            ("Pro", 29999, 44999, "6.7-inch 120Hz AMOLED, 108MP camera, 5G, 67W charging", "Flagship-style camera system, smooth 120Hz screen and fast charging for power users."),
            ("Ultra", 54999, 89999, "6.8-inch LTPO display, 200MP camera, 5G, wireless charging, 12GB RAM", "Top-end phone with a pro-grade camera, fast processor and premium build."),
        ],
    },
    "Laptops": {
        "brands": ["Vertex", "Kyros", "Aerolite", "Brightbyte"],
        "tiers": [
            ("Go 14", 32999, 44999, "14-inch FHD, 8GB RAM, 512GB SSD, 8-hour battery", "Light student laptop for notes, browsing and coding basics."),
            ("Work 15", 49999, 69999, "15.6-inch FHD IPS, 16GB RAM, 512GB SSD, backlit keyboard", "Reliable office laptop with a comfortable keyboard and plenty of memory."),
            ("Gamer X", 62999, 99999, "15.6-inch 144Hz, RTX graphics, 16GB RAM, 1TB SSD, RGB keyboard", "Gaming laptop with a dedicated GPU, high refresh screen and strong cooling."),
            ("Studio 16", 99999, 159999, "16-inch 4K OLED, 32GB RAM, 1TB SSD, colour-accurate display", "Creator laptop for video editing and design with a colour-accurate screen."),
        ],
    },
    "Headphones": {
        "brands": ["Sonara", "Echoform", "Beatrix", "Auralis"],
        "tiers": [
            ("Buds Air", 1499, 2999, "True wireless earbuds, 24-hour case battery, Bluetooth 5.3", "Compact wireless earbuds with clear calls and all-day battery."),
            ("Buds ANC", 3999, 7999, "Active noise cancellation, 30-hour battery, IPX4, low-latency gaming mode", "Noise-cancelling earbuds that block commute noise and last through a long day."),
            ("Over-Ear 500", 6999, 14999, "40mm drivers, ANC, 50-hour battery, foldable design", "Comfortable over-ear headphones with deep bass and very long battery life."),
            ("Studio Pro", 18999, 32999, "Hi-res audio, wired and wireless, 35-hour battery, memory-foam cushions", "Studio-tuned headphones for critical listening, mixing and travel."),
        ],
    },
    "Smartwatches": {
        "brands": ["Chronix", "Fitora", "Wristly"],
        "tiers": [
            ("Band 5", 1999, 3999, "1.4-inch display, heart-rate and SpO2 tracking, 10-day battery", "Affordable fitness band with sleep, steps and heart-rate tracking."),
            ("Active 2", 5999, 12999, "1.8-inch AMOLED, built-in GPS, 100+ sport modes, 7-day battery", "GPS watch for runners and gym users with a bright AMOLED screen."),
            ("Titan Elite", 17999, 34999, "Sapphire glass, GPS, ECG, LTE, 14-day battery, titanium case", "Premium rugged smartwatch with health sensors and very long battery life."),
        ],
    },
    "Cameras": {
        "brands": ["Optiq", "Lensora", "Framely"],
        "tiers": [
            ("Compact Z", 24999, 39999, "20MP sensor, 10x optical zoom, 4K video, flip screen", "Pocket camera with big zoom, ideal for travel and vlogging."),
            ("Mirror 24", 54999, 84999, "24MP mirrorless, 4K 60fps, in-body stabilisation, interchangeable lens", "Mirrorless camera with fast autofocus for photos and video."),
            ("Pro Full-Frame", 139999, 229999, "45MP full-frame sensor, 8K video, dual card slots, weather sealed", "Professional full-frame body for studio and event photography."),
        ],
    },
    "Tablets": {
        "brands": ["Slatewise", "Tabora", "Pandit"],
        "tiers": [
            ("Learn 10", 10999, 16999, "10.1-inch display, 4GB RAM, 64GB storage, kids mode", "Simple tablet for online classes, reading and video."),
            ("Air 11", 27999, 42999, "11-inch 90Hz display, 8GB RAM, 256GB storage, stylus support", "Slim tablet for note taking, sketching and streaming."),
            ("Max 13", 59999, 94999, "13-inch OLED, 12GB RAM, 512GB storage, keyboard cover support", "Large-screen tablet that can replace a laptop for light work."),
        ],
    },
}

SUFFIXES = ["", " Plus", " SE", " 2", " Max"]


def build_products():
    rows = []
    for category, info in CATALOG.items():
        for brand in info["brands"]:
            for tier, low, high, specs, desc in info["tiers"]:
                suffix = random.choice(SUFFIXES)
                if suffix.strip().isdigit() and tier[-1].isdigit():
                    suffix = ""
                price = int(round(random.randint(low, high) / 100.0) * 100) - 1
                rows.append(Product(
                    name=f"{brand} {tier}{suffix}",
                    brand=brand,
                    category=category,
                    price=max(price, 499),
                    rating=round(random.uniform(3.6, 4.8), 1),
                    description=desc,
                    specs=specs,
                    in_stock=random.random() > 0.08,
                ))
    return rows


if __name__ == "__main__":
    with app.app_context():
        if "--reset" in sys.argv:
            db.drop_all()
        db.create_all()
        if Product.query.count() == 0:
            db.session.add_all(build_products())
            db.session.commit()
            print(f"Seeded {Product.query.count()} products.")
        else:
            print("Products already exist. Use --reset to re-seed.")
        recommender.fit()
