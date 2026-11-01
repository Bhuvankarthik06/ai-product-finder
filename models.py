"""
models.py – SQLAlchemy ORM models.

Only one model is needed: Product.
The `to_dict()` method controls exactly what the API sends to the browser –
keep it explicit so we never accidentally leak internal fields.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Category icons shown in the UI (no external image needed for sample data).
CATEGORY_ICONS = {
    "Smartphones": "📱",
    "Laptops": "💻",
    "Headphones": "🎧",
    "Smartwatches": "⌚",
    "Cameras": "📷",
    "Tablets": "📲",
}


class Product(db.Model):
    __tablename__ = "products"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(160), nullable=False)
    brand       = db.Column(db.String(60),  nullable=False, index=True)
    category    = db.Column(db.String(60),  nullable=False, index=True)
    price       = db.Column(db.Integer,     nullable=False, index=True)   # INR
    rating      = db.Column(db.Float,       nullable=False, default=4.0,  index=True)
    description = db.Column(db.Text,        nullable=False)
    specs       = db.Column(db.Text,        nullable=False, default="")
    in_stock    = db.Column(db.Boolean,     nullable=False, default=True)

    def to_dict(self):
        """Return a plain dict safe to serialise as JSON.
        
        `icon` is derived server-side so the browser doesn't need to map categories itself.
        """
        return {
            "id":          self.id,
            "name":        self.name,
            "brand":       self.brand,
            "category":    self.category,
            "price":       self.price,
            "rating":      self.rating,
            "description": self.description,
            "specs":       self.specs,
            "in_stock":    self.in_stock,
            "icon":        CATEGORY_ICONS.get(self.category, "🛒"),
        }

    def text_blob(self):
        """Combined text used to build TF-IDF recommendation vectors."""
        return " ".join([self.name, self.brand, self.category, self.description, self.specs])
