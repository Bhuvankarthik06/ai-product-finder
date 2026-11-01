/**
 * app.js – AI Product Finder (v2.0)
 *
 * Full-featured interactive shopping experience:
 *  - Theme switching (Dark/Light mode) with localStorage persistence
 *  - AI natural language query parsing + smart rule-based fallback
 *  - Interactive category discovery pills & budget presets
 *  - Grid vs List view layout switcher
 *  - Persistent Wishlist (Favorites) stored in localStorage
 *  - Multi-product comparison dock & side-by-side modal
 *  - Active filter chips with one-click dismiss
 *  - XSS-safe DOM construction using textContent
 */

"use strict";

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const inr = (n) => "₹" + Number(n).toLocaleString("en-IN");

/** Build a DOM element without using innerHTML (XSS-safe). */
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "text") node.textContent = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c !== null && c !== undefined) node.append(c);
  }
  return node;
}

/** Fetch JSON with unified error handling. */
async function getJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let message = `Server error (${res.status}). Please try again.`;
    try {
      const data = await res.json();
      message = data.error || message;
    } catch (_) {}
    throw new Error(message);
  }
  return res.json();
}

/** Render ★★★★☆ style stars for a rating 1-5. */
function renderStars(rating) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.4 ? 1 : 0;
  const empty = Math.max(0, 5 - full - half);
  const span = el("span", { class: "stars" });
  span.textContent =
    "★".repeat(full) +
    (half ? "½" : "") +
    "☆".repeat(empty);
  return span;
}

// ---------------------------------------------------------------------------
// Application State
// ---------------------------------------------------------------------------
const state = {
  page: 1,
  pageSize: 12,
  total: 0,
  currentProducts: [],
  wishlist: new Set(JSON.parse(localStorage.getItem("ai_finder_wishlist") || "[]")),
  compareList: new Map(), // id -> product object
  theme: localStorage.getItem("ai_finder_theme") || "dark",
  viewMode: localStorage.getItem("ai_finder_view_mode") || "grid",
};

// ---------------------------------------------------------------------------
// Theme Management
// ---------------------------------------------------------------------------
function initTheme() {
  applyTheme(state.theme);
  const toggleBtn = $("theme-toggle");
  toggleBtn?.addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    localStorage.setItem("ai_finder_theme", state.theme);
    applyTheme(state.theme);
    showToast(`Switched to ${state.theme} mode`);
  });
}

function applyTheme(theme) {
  document.body.setAttribute("data-theme", theme);
  const icon = $("theme-icon");
  if (icon) {
    icon.textContent = theme === "dark" ? "🌙" : "☀️";
  }
}

// ---------------------------------------------------------------------------
// Toast Notifications
// ---------------------------------------------------------------------------
function showToast(message, duration = 3000) {
  const container = $("toast-container");
  const toast = el("div", { class: "toast", text: message });
  container.append(toast);
  setTimeout(() => {
    toast.remove();
  }, duration);
}

// ---------------------------------------------------------------------------
// Loading / Error UI
// ---------------------------------------------------------------------------
function showLoading() {
  $("loading").hidden = false;
  $("product-grid").hidden = true;
  $("error-banner").hidden = true;
  $("empty").hidden = true;
  $("pager").replaceChildren();
}

function hideLoading() {
  $("loading").hidden = true;
  $("product-grid").hidden = false;
}

function showError(message) {
  hideLoading();
  $("error-message").textContent = message;
  $("error-banner").hidden = false;
  $("product-grid").hidden = true;
  $("empty").hidden = true;
}

// ---------------------------------------------------------------------------
// Wishlist Management
// ---------------------------------------------------------------------------
function saveWishlist() {
  localStorage.setItem("ai_finder_wishlist", JSON.stringify([...state.wishlist]));
  updateWishlistUI();
}

function updateWishlistUI() {
  const countBadge = $("wishlist-count");
  if (countBadge) {
    countBadge.textContent = state.wishlist.size;
    countBadge.hidden = state.wishlist.size === 0;
  }
  // Update heart buttons on visible cards
  document.querySelectorAll(".card__wishlist-btn").forEach((btn) => {
    const id = parseInt(btn.dataset.id, 10);
    const active = state.wishlist.has(id);
    btn.classList.toggle("active", active);
    btn.textContent = active ? "❤️" : "🤍";
  });
}

function toggleWishlist(product) {
  if (state.wishlist.has(product.id)) {
    state.wishlist.delete(product.id);
    showToast(`Removed "${product.name}" from Saved`);
  } else {
    state.wishlist.add(product.id);
    showToast(`Saved "${product.name}" to Wishlist ❤️`);
  }
  saveWishlist();
}

// ---------------------------------------------------------------------------
// Comparison Management
// ---------------------------------------------------------------------------
function updateCompareUI() {
  const countBadge = $("compare-count");
  const dock = $("compare-dock");
  const dockText = $("compare-dock-text");
  const count = state.compareList.size;

  if (countBadge) {
    countBadge.textContent = count;
    countBadge.hidden = count === 0;
  }

  if (dock) {
    dock.hidden = count === 0;
    if (dockText) {
      dockText.textContent = `${count} product${count === 1 ? "" : "s"} selected to compare`;
    }
  }

  // Update card compare buttons
  document.querySelectorAll(".card__compare-btn").forEach((btn) => {
    const id = parseInt(btn.dataset.id, 10);
    const inCompare = state.compareList.has(id);
    btn.classList.toggle("active", inCompare);
    btn.textContent = inCompare ? "✓ Compare" : "+ Compare";
  });
}

function toggleCompare(product) {
  if (state.compareList.has(product.id)) {
    state.compareList.delete(product.id);
  } else {
    if (state.compareList.size >= 4) {
      showToast("You can compare up to 4 products at once.");
      return;
    }
    state.compareList.set(product.id, product);
    showToast(`Added "${product.name}" to comparison`);
  }
  updateCompareUI();
}

function openCompareModal() {
  if (state.compareList.size === 0) {
    showToast("Please select at least 1 product to compare.");
    return;
  }
  const modal = $("compare-modal");
  const body = $("compare-body");
  body.replaceChildren();

  const products = [...state.compareList.values()];

  const tableWrapper = el("div", { class: "compare-table-wrapper" });
  const table = el("table", { class: "compare-table" });

  // Header row
  const thead = el("thead");
  const headerRow = el("tr", {}, el("th", { text: "Feature" }));
  for (const p of products) {
    const th = el(
      "th",
      {},
      el("div", { style: "display:flex;align-items:center;justify-content:space-between;gap:8px;" },
        el("span", { text: p.name, style: "font-size:14px;font-weight:700;" }),
        el("button", {
          type: "button",
          style: "color:var(--error);font-size:16px;cursor:pointer;",
          text: "✕",
          title: "Remove from comparison",
          onclick: () => {
            state.compareList.delete(p.id);
            updateCompareUI();
            if (state.compareList.size === 0) {
              modal.close();
            } else {
              openCompareModal();
            }
          },
        })
      )
    );
    headerRow.append(th);
  }
  thead.append(headerRow);
  table.append(thead);

  // Table Body Rows
  const tbody = el("tbody");

  const rows = [
    ["Icon", (p) => el("span", { style: "font-size:32px;", text: p.icon || "🛒" })],
    ["Category", (p) => el("span", { text: p.category })],
    ["Brand", (p) => el("span", { text: p.brand })],
    ["Price", (p) => el("span", { style: "font-weight:800;color:var(--accent-light);", text: inr(p.price) })],
    ["Rating", (p) => el("span", { text: `★ ${p.rating} / 5` })],
    ["Availability", (p) => el("span", {
      class: p.in_stock ? "card__stock-badge card__stock-badge--in" : "card__stock-badge card__stock-badge--out",
      text: p.in_stock ? "In Stock" : "Out of Stock"
    })],
    ["Specifications", (p) => el("span", { text: p.specs })],
    ["Description", (p) => el("span", { style: "font-size:12px;color:var(--muted-text);", text: p.description })],
    ["Action", (p) => el("button", {
      type: "button",
      class: "btn-primary btn-sm",
      text: "View Details",
      onclick: () => {
        modal.close();
        openDetail(p.id);
      }
    })],
  ];

  for (const [label, renderFn] of rows) {
    const tr = el("tr", {}, el("td", { style: "font-weight:700;color:var(--muted-text);", text: label }));
    for (const p of products) {
      tr.append(el("td", {}, renderFn(p)));
    }
    tbody.append(tr);
  }

  table.append(tbody);
  tableWrapper.append(table);
  body.append(tableWrapper);

  if (!modal.open) modal.showModal();
}

// ---------------------------------------------------------------------------
// Wishlist Modal
// ---------------------------------------------------------------------------
async function openWishlistModal() {
  const modal = $("wishlist-modal");
  const body = $("wishlist-body");
  body.replaceChildren();

  if (state.wishlist.size === 0) {
    body.append(
      el("div", { class: "empty-state" },
        el("div", { class: "empty-state__icon", text: "🤍" }),
        el("h3", { class: "empty-state__title", text: "Your wishlist is empty" }),
        el("p", { class: "empty-state__text", text: "Click the heart icon on any product card to save it here for later." }),
        el("button", {
          type: "button",
          class: "btn-primary",
          text: "Browse Catalog",
          onclick: () => modal.close(),
        })
      )
    );
  } else {
    const list = el("ul", { style: "display:flex;flex-direction:column;gap:12px;" });
    for (const id of state.wishlist) {
      try {
        const p = await getJSON(`/api/products/${id}`);
        list.append(
          el("li", {
            style: "display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--surface-alt);border:1px solid var(--border);border-radius:var(--r-md);gap:16px;"
          },
            el("div", { style: "display:flex;align-items:center;gap:12px;flex:1;min-width:0;" },
              el("span", { style: "font-size:24px;", text: p.icon || "🛒" }),
              el("div", { style: "min-width:0;flex:1;" },
                el("p", { style: "font-size:14px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;", text: p.name }),
                el("p", { style: "font-size:12px;color:var(--muted-text);", text: `${p.brand} · ${inr(p.price)}` }),
              )
            ),
            el("div", { style: "display:flex;align-items:center;gap:8px;" },
              el("button", {
                type: "button",
                class: "btn-primary btn-sm",
                text: "View",
                onclick: () => {
                  modal.close();
                  openDetail(p.id);
                }
              }),
              el("button", {
                type: "button",
                style: "color:var(--error);font-size:16px;padding:4px 8px;cursor:pointer;",
                text: "✕",
                title: "Remove from Saved",
                onclick: () => {
                  toggleWishlist(p);
                  openWishlistModal();
                }
              })
            )
          )
        );
      } catch (_) {}
    }
    body.append(list);
  }

  if (!modal.open) modal.showModal();
}

// ---------------------------------------------------------------------------
// Sidebar Filter Controls
// ---------------------------------------------------------------------------
function currentFilters() {
  return {
    q: $("f-q").value.trim(),
    category: $("f-category").value,
    brand: $("f-brand").value,
    min_price: $("f-min").value,
    max_price: $("f-max").value,
    min_rating: $("f-rating").value,
    in_stock: $("f-stock").checked ? "true" : "",
    sort: $("f-sort").value,
    page: state.page,
  };
}

/** Apply a filter dict returned by the assistant to the sidebar controls. */
function applyFiltersToSidebar(f) {
  if (f.category) {
    $("f-category").value = f.category;
    updateCategoryPills(f.category);
  }
  if (f.brand) $("f-brand").value = f.brand;
  if (f.min_price != null) $("f-min").value = f.min_price;
  if (f.max_price != null) $("f-max").value = f.max_price;
  if (f.min_rating != null) {
    const opts = [...$("f-rating").options].map((o) => parseFloat(o.value) || 0);
    const best = [...$("f-rating").options].find(
      (o) => parseFloat(o.value) === Math.max(...opts.filter((v) => v <= f.min_rating))
    );
    if (best) $("f-rating").value = best.value;
    updateRatingPills(f.min_rating);
  }
  if (f.sort) {
    $("f-sort").value = f.sort;
    $("toolbar-sort").value = f.sort;
  }
  updateSearchClearBtn();
}

function resetFilters() {
  ["f-q", "f-min", "f-max"].forEach((id) => ($(id).value = ""));
  ["f-category", "f-brand", "f-rating"].forEach((id) => ($(id).value = ""));
  $("f-stock").checked = false;
  $("f-sort").value = "relevance";
  $("toolbar-sort").value = "relevance";

  updateCategoryPills("");
  updateRatingPills("");
  updateSearchClearBtn();
  hideAiResult();
  state.page = 1;
  loadProducts();
}

function updateCategoryPills(activeCategory) {
  document.querySelectorAll(".cat-pill").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.category === activeCategory);
  });
}

function updateRatingPills(ratingVal) {
  document.querySelectorAll(".rating-pill").forEach((btn) => {
    btn.classList.toggle("active", String(btn.dataset.rating) === String(ratingVal || ""));
  });
}

// ---------------------------------------------------------------------------
// Active Tags Bar
// ---------------------------------------------------------------------------
function updateActiveTagsBar() {
  const f = currentFilters();
  const list = $("active-tags-list");
  const bar = $("active-tags-bar");
  const countBadge = $("active-filter-count");

  list.replaceChildren();

  const activeItems = [];
  if (f.q) activeItems.push({ label: `Search: "${f.q}"`, clear: () => { $("f-q").value = ""; updateSearchClearBtn(); } });
  if (f.category) activeItems.push({ label: `Category: ${f.category}`, clear: () => { $("f-category").value = ""; updateCategoryPills(""); } });
  if (f.brand) activeItems.push({ label: `Brand: ${f.brand}`, clear: () => { $("f-brand").value = ""; } });
  if (f.min_price && f.max_price) activeItems.push({ label: `Price: ${inr(f.min_price)} – ${inr(f.max_price)}`, clear: () => { $("f-min").value = ""; $("f-max").value = ""; } });
  else if (f.min_price) activeItems.push({ label: `Min: ${inr(f.min_price)}`, clear: () => { $("f-min").value = ""; } });
  else if (f.max_price) activeItems.push({ label: `Max: ${inr(f.max_price)}`, clear: () => { $("f-max").value = ""; } });
  if (f.min_rating) activeItems.push({ label: `Rating: ${f.min_rating}★+`, clear: () => { $("f-rating").value = ""; updateRatingPills(""); } });
  if (f.in_stock === "true") activeItems.push({ label: "In Stock Only", clear: () => { $("f-stock").checked = false; } });

  const activeCount = activeItems.length;
  if (countBadge) {
    countBadge.textContent = activeCount;
    countBadge.hidden = activeCount === 0;
  }

  if (activeCount === 0) {
    bar.hidden = true;
    return;
  }

  bar.hidden = false;
  for (const item of activeItems) {
    const tag = el("span", { class: "active-tag" },
      el("span", { text: item.label }),
      el("button", {
        type: "button",
        class: "active-tag__close",
        text: "✕",
        "aria-label": `Remove ${item.label}`,
        onclick: () => {
          item.clear();
          state.page = 1;
          loadProducts();
        }
      })
    );
    list.append(tag);
  }
}

// ---------------------------------------------------------------------------
// AI Result Panel
// ---------------------------------------------------------------------------
function showAiResult(filters, source, relaxed) {
  const badge = $("ai-source-badge");
  const summary = $("ai-summary");
  const chips = $("ai-chips");

  badge.textContent = source === "llm" ? "🤖 AI Semantic" : "📐 Rules Engine";
  summary.textContent = describeFilters(filters) || "matching all filters";

  chips.replaceChildren();
  const pairs = [
    ["Category", filters.category],
    ["Brand", filters.brand],
    ["Min price", filters.min_price != null ? inr(filters.min_price) : null],
    ["Max price", filters.max_price != null ? inr(filters.max_price) : null],
    ["Min rating", filters.min_rating != null ? `${filters.min_rating}★` : null],
    ["Sort", filters.sort && filters.sort !== "relevance"
      ? { price_asc: "cheapest first", price_desc: "priciest first", rating_desc: "top rated" }[filters.sort]
      : null],
    ...(filters.keywords || []).map((k) => ["Feature", k]),
  ];

  for (const [key, val] of pairs) {
    if (!val) continue;
    chips.append(
      el("span", { class: "ai-chip" },
        el("span", { class: "ai-chip__key", text: key + ":" }),
        el("span", { text: val })
      )
    );
  }

  if (relaxed) {
    $("relaxed-note").hidden = false;
  }

  $("ai-result").hidden = false;
}

function hideAiResult() {
  $("ai-result").hidden = true;
  $("relaxed-note").hidden = true;
  $("ask-input").value = "";
  $("ask-clear").hidden = true;
}

function describeFilters(f) {
  const parts = [];
  if (f.category) parts.push(f.category.toLowerCase());
  if (f.brand) parts.push(`brand ${f.brand}`);
  if (f.min_price != null && f.max_price != null) parts.push(`${inr(f.min_price)} to ${inr(f.max_price)}`);
  else if (f.max_price != null) parts.push(`under ${inr(f.max_price)}`);
  else if (f.min_price != null) parts.push(`above ${inr(f.min_price)}`);
  if (f.min_rating) parts.push(`rated ${f.min_rating}+`);
  if (f.keywords?.length) parts.push(`features: ${f.keywords.join(", ")}`);
  const sortLabels = { price_asc: "cheapest first", price_desc: "priciest first", rating_desc: "top rated" };
  if (f.sort && f.sort !== "relevance") parts.push(sortLabels[f.sort]);
  return parts.join(" · ");
}

// ---------------------------------------------------------------------------
// Product Card Construction
// ---------------------------------------------------------------------------
function productCard(p, onOpen) {
  const open = () => onOpen(p.id);

  // Simulated original price and discount for realistic e-commerce appearance
  const discountRate = 10 + (p.id % 20); // 10% to 29%
  const originalPrice = Math.round((p.price * 100) / (100 - discountRate));

  const stockBadge = el(
    "span",
    {
      class: p.in_stock
        ? "card__stock-badge card__stock-badge--in"
        : "card__stock-badge card__stock-badge--out",
      text: p.in_stock ? "● In stock" : "○ Out of stock",
    }
  );

  const isSaved = state.wishlist.has(p.id);
  const wishlistBtn = el(
    "button",
    {
      type: "button",
      class: `card__wishlist-btn ${isSaved ? "active" : ""}`,
      "data-id": String(p.id),
      "aria-label": isSaved ? "Remove from wishlist" : "Add to wishlist",
      onclick: (e) => {
        e.stopPropagation();
        toggleWishlist(p);
      },
    },
    el("span", { text: isSaved ? "❤️" : "🤍" })
  );

  const isInCompare = state.compareList.has(p.id);
  const compareBtn = el(
    "button",
    {
      type: "button",
      class: `btn-ghost btn-sm card__compare-btn ${isInCompare ? "active" : ""}`,
      "data-id": String(p.id),
      onclick: (e) => {
        e.stopPropagation();
        toggleCompare(p);
      },
      text: isInCompare ? "✓ Compare" : "+ Compare",
    }
  );

  const card = el(
    "li",
    {
      class: "card",
      tabindex: "0",
      role: "button",
      "aria-label": `${p.name}, ${inr(p.price)}`,
      onclick: open,
      onkeydown: (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      },
    },
    // Top floating actions
    el(
      "div",
      { class: "card__top-actions" },
      stockBadge,
      el("div", { class: "card__action-btn-group" }, compareBtn, wishlistBtn)
    ),
    // Thumbnail container
    el(
      "div",
      { class: "card__thumb" },
      el("span", { text: p.icon || "🛒" }),
      el("span", { class: "card__discount-tag", text: `${discountRate}% OFF` })
    ),
    // Body content
    el(
      "div",
      { class: "card__body" },
      el(
        "div",
        { class: "card__meta-row" },
        el("span", { class: "card__category", text: p.category }),
        el("span", { class: "card__brand", text: p.brand })
      ),
      el("h3", { class: "card__name", text: p.name }),
      el("p", { class: "card__specs", text: p.specs })
    ),
    // Card footer: price and rating
    el(
      "div",
      { class: "card__footer" },
      el(
        "div",
        { class: "card__price-wrap" },
        el("span", { class: "card__price", text: inr(p.price) }),
        el("span", { class: "card__original-price", text: inr(originalPrice) })
      ),
      el(
        "div",
        { class: "card__rating-wrap" },
        renderStars(p.rating),
        el("span", { text: ` ${p.rating}` })
      )
    )
  );

  return card;
}

// ---------------------------------------------------------------------------
// Render Results
// ---------------------------------------------------------------------------
function render(items, total) {
  hideLoading();
  state.currentProducts = items;

  const grid = $("product-grid");
  grid.replaceChildren(...items.map((p) => productCard(p, openDetail)));

  $("empty").hidden = items.length > 0;
  $("error-banner").hidden = true;
  $("relaxed-note").hidden = true;

  state.total = total;
  const countEl = $("count");
  countEl.textContent = total
    ? `${total.toLocaleString()} product${total === 1 ? "" : "s"} found`
    : "No products";

  $("header-count").textContent = total ? `${total.toLocaleString()} in catalog` : "0 products";

  updateActiveTagsBar();
  updateWishlistUI();
  updateCompareUI();
  renderPager(total);
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------
function renderPager(total) {
  const pages = Math.ceil(total / state.pageSize);
  const pager = $("pager");
  pager.replaceChildren();
  if (pages <= 1) return;

  const current = state.page;

  function addBtn(label, pageNum, isCurrent = false, title = "") {
    const b = el("button", {
      type: "button",
      class: "pager__btn",
      text: String(label),
      onclick: () => {
        state.page = pageNum;
        loadProducts();
        $("product-grid").scrollIntoView({ behavior: "smooth", block: "start" });
      },
    });
    if (title) b.title = title;
    if (isCurrent) b.setAttribute("aria-current", "page");
    pager.append(b);
  }

  function addEllipsis() {
    pager.append(el("span", { class: "pager__ellipsis", text: "…" }));
  }

  if (current > 1) addBtn("‹", current - 1, false, "Previous page");

  if (pages <= 7) {
    for (let i = 1; i <= pages; i++) addBtn(i, i, i === current);
  } else {
    addBtn(1, 1, current === 1);
    if (current > 3) addEllipsis();
    const start = Math.max(2, current - 1);
    const end = Math.min(pages - 1, current + 1);
    for (let i = start; i <= end; i++) addBtn(i, i, i === current);
    if (current < pages - 2) addEllipsis();
    addBtn(pages, pages, current === pages);
  }

  if (current < pages) addBtn("›", current + 1, false, "Next page");
}

// ---------------------------------------------------------------------------
// Load Products
// ---------------------------------------------------------------------------
async function loadProducts() {
  showLoading();
  try {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(currentFilters())) {
      if (v !== "" && v !== null && v !== undefined) params.set(k, v);
    }
    const data = await getJSON("/api/products?" + params);
    state.pageSize = data.page_size;
    if (data.relaxed) $("relaxed-note").hidden = false;
    render(data.items, data.total);
  } catch (err) {
    showError(err.message);
  }
}

// ---------------------------------------------------------------------------
// Product Detail Modal
// ---------------------------------------------------------------------------
async function openDetail(id) {
  const modal = $("detail-modal");
  $("detail-body").replaceChildren();
  $("detail-loading").hidden = false;
  if (!modal.open) modal.showModal();
  modal.querySelector(".detail-modal__inner").scrollTop = 0;

  try {
    const [p, simData] = await Promise.all([
      getJSON(`/api/products/${id}`),
      getJSON(`/api/products/${id}/similar`),
    ]);
    $("detail-loading").hidden = true;

    const stockClass = p.in_stock
      ? "detail-stock detail-stock--in"
      : "detail-stock detail-stock--out";
    const stockText = p.in_stock ? "✓ In Stock" : "✕ Out of Stock";

    const discountRate = 10 + (p.id % 20);
    const originalPrice = Math.round((p.price * 100) / (100 - discountRate));

    const body = $("detail-body");
    body.replaceChildren(
      // Hero header
      el(
        "div",
        { class: "detail-hero-box" },
        el("div", { class: "detail-icon-showcase", text: p.icon || "🛒" }),
        el(
          "div",
          { class: "detail-title-col" },
          el("span", { class: "detail-category-badge", text: p.category }),
          el("h2", { id: "detail-name", class: "detail-name", text: p.name }),
          el("p", { class: "detail-brand-badge", text: `by ${p.brand}` })
        )
      ),
      // Price & Stock
      el(
        "div",
        { class: "detail-price-row" },
        el("span", { class: "detail-price", text: inr(p.price) }),
        el("span", { class: "card__original-price", text: inr(originalPrice) }),
        el("span", { class: "card__discount-tag", text: `${discountRate}% OFF` }),
        el("span", { class: stockClass, text: stockText })
      ),
      // Description
      el("p", { class: "detail-description", style: "margin-bottom:16px;line-height:1.6;", text: p.description }),
      // Specs box
      el(
        "div",
        { class: "detail-specs-box" },
        el("p", { class: "detail-specs-label", text: "Key Specifications & Features" }),
        el("p", { class: "detail-specs-text", text: p.specs })
      ),
      // Rating row
      el(
        "div",
        { style: "display:flex;align-items:center;gap:8px;margin-bottom:20px;" },
        renderStars(p.rating),
        el("span", { style: "font-weight:700;", text: `${p.rating} out of 5` }),
        el("span", { style: "color:var(--muted-text);font-size:13px;", text: "• Verified Ratings" })
      ),
      // Action Buttons
      el(
        "div",
        { class: "detail-actions-row" },
        el(
          "button",
          {
            type: "button",
            class: "btn-action btn-action-primary",
            onclick: () => {
              showToast(`✓ Order placed for "${p.name}" (Demo checkout)`);
            },
          },
          el("span", { text: "⚡ Buy Now (Demo)" })
        ),
        el(
          "button",
          {
            type: "button",
            class: "btn-action btn-action-secondary",
            onclick: () => {
              toggleWishlist(p);
            },
          },
          el("span", { text: state.wishlist.has(p.id) ? "❤️ Saved" : "🤍 Save to Wishlist" })
        ),
        el(
          "button",
          {
            type: "button",
            class: "btn-action btn-action-secondary",
            onclick: () => {
              toggleCompare(p);
            },
          },
          el("span", { text: "⚖️ Compare" })
        )
      )
    );

    // Similar products recommendation list (TF-IDF + Cosine similarity)
    if (simData.items?.length) {
      const simList = el("ul", { class: "similar__list" });
      for (const s of simData.items) {
        simList.append(
          el(
            "li",
            {
              class: "similar__item",
              tabindex: "0",
              onclick: () => openDetail(s.id),
              onkeydown: (e) => {
                if (e.key === "Enter") openDetail(s.id);
              },
            },
            el("span", { class: "similar__icon", text: s.icon || "🛒" }),
            el(
              "div",
              { class: "similar__info" },
              el("p", { class: "similar__name", text: s.name }),
              el("p", { class: "similar__meta", text: `${s.brand} · ${s.category}` })
            ),
            el("span", { class: "similar__price", text: inr(s.price) })
          )
        );
      }
      body.append(
        el(
          "section",
          { class: "similar" },
          el("h3", { class: "similar__title", text: "✨ Similar Products (AI Content Recommendations)" }),
          simList
        )
      );
    }
  } catch (err) {
    $("detail-loading").hidden = true;
    $("detail-body").append(
      el("p", { text: err.message, style: "color:var(--error);padding:20px" })
    );
  }
}

// ---------------------------------------------------------------------------
// AI Assistant
// ---------------------------------------------------------------------------
async function ask(query) {
  const btn = $("ask-btn");
  const textSpan = btn.querySelector(".ask-btn__text");
  const spinnerSpan = btn.querySelector(".ask-btn__spinner");
  btn.disabled = true;
  textSpan.textContent = "Analyzing…";
  spinnerSpan.hidden = false;
  $("relaxed-note").hidden = true;

  try {
    const data = await getJSON("/api/assistant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    applyFiltersToSidebar(data.filters);
    showAiResult(data.filters, data.source, data.relaxed);
    state.page = 1;
    render(data.items, data.total);
    $("product-grid").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showToast("⚠️ " + err.message);
  } finally {
    btn.disabled = false;
    textSpan.textContent = "Find Products";
    spinnerSpan.hidden = true;
  }
}

// ---------------------------------------------------------------------------
// Clear Button Visibility
// ---------------------------------------------------------------------------
function updateSearchClearBtn() {
  $("f-q-clear").hidden = $("f-q").value === "";
}

// ---------------------------------------------------------------------------
// View Mode (Grid vs List)
// ---------------------------------------------------------------------------
function initViewMode() {
  const grid = $("product-grid");
  const btnGrid = $("view-grid");
  const btnList = $("view-list");

  function setView(mode) {
    state.viewMode = mode;
    localStorage.setItem("ai_finder_view_mode", mode);
    grid.classList.toggle("list-view", mode === "list");
    btnGrid.classList.toggle("active", mode === "grid");
    btnList.classList.toggle("active", mode === "list");
    btnGrid.setAttribute("aria-pressed", String(mode === "grid"));
    btnList.setAttribute("aria-pressed", String(mode === "list"));
  }

  btnGrid?.addEventListener("click", () => setView("grid"));
  btnList?.addEventListener("click", () => setView("list"));

  setView(state.viewMode);
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
async function init() {
  initTheme();
  initViewMode();

  // Load catalog metadata for category and brand dropdowns
  try {
    const meta = await getJSON("/api/meta");
    for (const c of meta.categories) {
      $("f-category").append(el("option", { value: c, text: c }));
    }
    for (const b of meta.brands) {
      $("f-brand").append(el("option", { value: b, text: b }));
    }
  } catch (err) {
    showToast("Could not load catalog metadata.");
  }

  // AI Ask Form
  $("ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("ask-input").value.trim();
    if (q) ask(q);
  });

  $("ask-input").addEventListener("input", () => {
    $("ask-clear").hidden = $("ask-input").value === "";
  });

  $("ask-clear").addEventListener("click", () => {
    $("ask-input").value = "";
    $("ask-clear").hidden = true;
  });

  // Example Prompt Chips
  document.querySelectorAll(".eg-chip").forEach((b) =>
    b.addEventListener("click", () => {
      const cleanText = b.textContent.replace(/^[^\w\s]+/, "").trim();
      $("ask-input").value = cleanText;
      $("ask-clear").hidden = false;
      ask(cleanText);
    })
  );

  // Category Quick-Select Pills in Hero
  document.querySelectorAll(".cat-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cat = btn.dataset.category;
      updateCategoryPills(cat);
      $("f-category").value = cat;
      state.page = 1;
      loadProducts();
      $("product-grid").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // Budget Presets in Sidebar
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      $("f-min").value = btn.dataset.min || "";
      $("f-max").value = btn.dataset.max || "";
      state.page = 1;
      loadProducts();
    });
  });

  // Star Rating Quick Pills in Sidebar
  document.querySelectorAll(".rating-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      const val = btn.dataset.rating || "";
      updateRatingPills(val);
      $("f-rating").value = val;
      state.page = 1;
      loadProducts();
    });
  });

  // In-Stock Checkbox
  $("f-stock").addEventListener("change", () => {
    state.page = 1;
    loadProducts();
  });

  // Sidebar Debounce for Text and Number inputs
  let debounceTimer;
  const debounce = () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.page = 1;
      loadProducts();
    }, 300);
  };

  ["f-q", "f-min", "f-max"].forEach((id) => $(id).addEventListener("input", debounce));

  ["f-category", "f-brand", "f-rating", "f-sort"].forEach((id) =>
    $(id).addEventListener("change", () => {
      if (id === "f-category") updateCategoryPills($(id).value);
      if (id === "f-rating") updateRatingPills($(id).value);
      if (id === "f-sort") $("toolbar-sort").value = $(id).value;
      state.page = 1;
      loadProducts();
    })
  );

  // Toolbar Sort Sync
  $("toolbar-sort").addEventListener("change", () => {
    $("f-sort").value = $("toolbar-sort").value;
    state.page = 1;
    loadProducts();
  });

  // Clear button on search text box
  $("f-q").addEventListener("input", updateSearchClearBtn);
  $("f-q-clear").addEventListener("click", () => {
    $("f-q").value = "";
    updateSearchClearBtn();
    state.page = 1;
    loadProducts();
  });

  // Reset buttons
  $("f-reset").addEventListener("click", resetFilters);
  $("empty-reset").addEventListener("click", resetFilters);
  $("ai-clear").addEventListener("click", resetFilters);
  $("clear-all-tags-btn")?.addEventListener("click", resetFilters);

  // Error retry
  $("error-retry").addEventListener("click", loadProducts);

  // Detail Modal Controls
  $("detail-close").addEventListener("click", () => $("detail-modal").close());
  $("detail-modal").addEventListener("click", (e) => {
    if (e.target === $("detail-modal")) $("detail-modal").close();
  });
  $("detail-modal").addEventListener("cancel", () => $("detail-modal").close());

  // Comparison Modal Controls
  $("compare-nav-btn")?.addEventListener("click", openCompareModal);
  $("compare-dock-btn")?.addEventListener("click", openCompareModal);
  $("compare-dock-clear")?.addEventListener("click", () => {
    state.compareList.clear();
    updateCompareUI();
    showToast("Cleared comparison list");
  });
  $("compare-close")?.addEventListener("click", () => $("compare-modal").close());
  $("compare-modal")?.addEventListener("click", (e) => {
    if (e.target === $("compare-modal")) $("compare-modal").close();
  });

  // Wishlist Modal Controls
  $("wishlist-btn")?.addEventListener("click", openWishlistModal);
  $("wishlist-close")?.addEventListener("click", () => $("wishlist-modal").close());
  $("wishlist-modal")?.addEventListener("click", (e) => {
    if (e.target === $("wishlist-modal")) $("wishlist-modal").close();
  });

  // Mobile Filter Drawer Toggle
  const sidebar = document.querySelector(".sidebar");
  const filterToggle = $("filter-toggle");
  filterToggle?.addEventListener("click", () => {
    const isOpen = sidebar.classList.toggle("is-open");
    filterToggle.setAttribute("aria-expanded", String(isOpen));
  });

  // Initial Product Load & UI Setup
  updateWishlistUI();
  updateCompareUI();
  loadProducts();
}

init();
