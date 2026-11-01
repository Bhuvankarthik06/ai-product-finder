# AI-Powered E-Commerce Product Finder (v2.0)

Full-stack product search and discovery platform built with **Python, Flask, SQLAlchemy, JavaScript, scikit-learn, and an LLM API**.

## ✨ Features

- **AI Natural Language Shopping Assistant**: Describe what you want in plain English (e.g. *"laptop for gaming under 90k"* or *"noise cancelling earbuds below 8000"*). The AI extracts structured filters and searches the catalog.
- **Smart Rule-Based Fallback**: Works completely offline or without an API key using an automated rule-based NLP parser.
- **Content-Based Recommendations**: Powered by scikit-learn's `TfidfVectorizer` and cosine similarity to surface similar products in real time.
- **Modern Responsive UI (v2.0)**:
  - 🌙 **Dark & Light Mode Toggle**: One-click theme switcher with persistent local storage.
  - 📱 **Quick Category Discovery Pills**: Direct filtering for Smartphones, Laptops, Audio, Smartwatches, and more.
  - 💰 **Quick Budget Presets & Star Rating Filters**: Rapid one-tap price ranges (< ₹15k, ₹15k–40k, etc.) and rating pills.
  - ⊞ / ☰ **Grid vs. List View**: Switch between responsive visual card grid and detailed list view.
  - ❤️ **Wishlist / Saved Items**: Save favorite products with instant persistence in local storage and a dedicated drawer.
  - ⚖️ **Product Comparison Dock & Matrix**: Select up to 4 products and compare specs, price, stock, and ratings side-by-side in a floating comparison modal.
  - 🏷️ **Active Filters Bar**: Visual chips for all active filters with one-click individual removal.
  - ⚡ **Stock Availability Filter**: Instant filter for "In Stock Only" items.
  - 🔍 **Live Search with Debounce**: Responsive instant text search.

> Sample data uses fictional brands and generated prices (in INR) so the project runs out of the box.

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone https://github.com/<your-username>/ai-product-finder.git
cd ai-product-finder

# 2. Set up virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (optional)
cp .env.example .env

# 5. Seed the database with sample products
python seed.py

# 6. Start the Flask application
python app.py
# Open http://127.0.0.1:5000 in your browser
```

### Database
- **SQLite (Default):** Runs immediately out of the box with zero setup.
- **MySQL:** Set `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/product_finder` in `.env`.

### LLM Assistant (Optional)
Set `ANTHROPIC_API_KEY` in `.env` to connect Claude. Without a key (or if the API is unreachable), the assistant automatically falls back to the built-in rule-based parser.

## 📁 Project Structure

```
ai-product-finder/
├── app.py            # Flask application factory and REST API routes
├── config.py         # Configuration settings & environment variables
├── models.py         # SQLAlchemy Product model
├── search.py         # Structured SQL filters & TF-IDF relevance ranking
├── recommender.py    # TF-IDF + cosine similarity engine (scikit-learn)
├── llm_assistant.py  # LLM query parser + rule-based fallback
├── seed.py           # Sample data loader with 79 products
├── schema.sql        # MySQL database schema (optional)
├── requirements.txt  # Python package dependencies
├── templates/
│   └── index.html    # Modern HTML5 template
├── static/
│   ├── style.css     # Design system, glassmorphism, responsive styles
│   └── app.js        # Vanilla JS frontend with Fetch API & state management
└── tests/            # Automated test suite
```

## 🔌 API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/meta` | Categories, brands, price range |
| `GET` | `/api/products` | Search/filter: `q, category, brand, min_price, max_price, min_rating, in_stock, sort, page` |
| `GET` | `/api/products/<id>` | Full product details |
| `GET` | `/api/products/<id>/similar` | Top 4 similar products (TF-IDF + cosine similarity) |
| `POST` | `/api/assistant` | Natural language shopping query: `{"query": "..."}` |

## 🛡️ Security & Reliability

- **SQL Injection Prevention**: SQLAlchemy parameterized queries across all database filters.
- **XSS Protection**: Frontend elements constructed dynamically with `textContent` (never unsafe `innerHTML`).
- **Server-side Security**: API keys stay securely on the server; client queries capped in length.
