/**
 * Myntra Analytics Dashboard — Enterprise Frontend
 */
const state = {
  page: 1,
  limit: 10,
  totalPages: 1,
  lastScraped: [],
  charts: {},
  scrapeSessions: 0,
};

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initScrapeForm();
  initFilters();
  initPagination();
  initDarkMode();
  initSidebarToggle();
  initExportButtons();
  refreshDashboard();
});

/* ─── NAVIGATION ─── */
function initNavigation() {
  document.querySelectorAll('.nav-link[data-view]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      showView(link.dataset.view);
    });
  });
  document.getElementById('nav-export')?.addEventListener('click', e => {
    e.preventDefault();
    document.querySelector('.export-row')?.scrollIntoView({ behavior: 'smooth' });
  });
}

function showView(view) {
  document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
  const map = {
    dashboard: 'view-dashboard',
    saved: 'view-dashboard',
    analytics: 'view-analytics',
    recommendations: 'view-recommendations',
    mongodb: 'view-mongodb',
    logs: 'view-logs',
    settings: 'view-settings',
  };
  document.getElementById(map[view] || 'view-dashboard')?.classList.add('active');
  if (view === 'analytics') loadAnalyticsView();
  if (view === 'recommendations') loadRecommendations();
  if (view === 'mongodb') loadMongoStats();
  if (view === 'logs') loadLogs();
  if (view === 'settings') loadSettings();
}

/* ─── SCRAPE ─── */
function initScrapeForm() {
  document.getElementById('scrape-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const query = document.getElementById('search-query')?.value.trim() || '';
    const url = document.getElementById('product-url')?.value.trim() || '';
    const count = clampCount();
    const category = document.getElementById('category-select')?.value || '';

    if (!query && !url) {
      showAlert('Enter a product name or Myntra URL.', 'warning');
      return;
    }
    if (url && !validateUrl(url)) return;

    const payload = { product_count: count, category };
    if (url) payload.product_url = url;
    else payload.query = query;

    const msg = url
      ? 'Scraping product from URL...'
      : `Searching "${query}" — scraping ${count} product(s)...`;
    showLoader(true, msg);

    try {
      const res = await fetch('/api/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      showLoader(false);

      if (res.ok && data.status === 'success') {
        state.lastScraped = data.data || [];
        state.scrapeSessions++;
        showAlert(data.message || `Scraped ${data.scraped_count} product(s).`, 'success');
        document.getElementById('search-query').value = '';
        document.getElementById('product-url').value = '';
        await refreshDashboard(state.lastScraped);
        renderProducts(state.lastScraped, state.lastScraped.length);
        document.getElementById('page-info').textContent =
          `Showing ${state.lastScraped.length} scraped product(s)`;
      } else {
        showAlert(data.message || 'Scraping failed.', 'error');
      }
    } catch {
      showLoader(false);
      showAlert('Network error. Check your connection.', 'error');
    }
  });
}

function clampCount() {
  const el = document.getElementById('product-count');
  if (!el) return 3;
  let v = parseInt(el.value, 10);
  if (isNaN(v)) v = 3;
  v = Math.min(50, Math.max(1, v));
  el.value = v;
  return v;
}

function validateUrl(input) {
  let url = input.trim();
  if (url.startsWith('www.')) url = 'https://' + url;
  else if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
  try {
    const p = new URL(url);
    if (!p.hostname.includes('myntra.com')) {
      showAlert('Invalid URL. Use a myntra.com product link.', 'error');
      return false;
    }
    return true;
  } catch {
    showAlert('Invalid URL format.', 'error');
    return false;
  }
}

/* ─── DATA LOADING ─── */
async function refreshDashboard(highlightProducts) {
  await Promise.all([
    loadStats(),
    loadFilters(),
    highlightProducts ? Promise.resolve() : loadProducts(),
    loadCharts(highlightProducts),
  ]);
}

async function loadStats() {
  try {
    const res = await fetch('/api/dashboard-stats');
    const { data } = await res.json();
    if (!data) return;
    document.getElementById('card-total-products').textContent = data.total_products || 0;
    document.getElementById('card-avg-price').textContent =
      '₹' + Math.round(data.avg_price || 0).toLocaleString('en-IN');
    document.getElementById('card-brands').textContent = data.brands_found || 0;
    document.getElementById('card-avg-rating').textContent =
      (data.avg_rating ? data.avg_rating.toFixed(1) : '0') + '/5';
    document.getElementById('stat-sidebar-products').textContent = data.total_products || 0;
    document.getElementById('stat-pages').textContent = state.scrapeSessions;
    document.getElementById('stat-updated').textContent =
      new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  } catch (e) { console.error(e); }
}

async function loadFilters() {
  try {
    const res = await fetch('/api/products/filters');
    const { data } = await res.json();
    if (!data) return;
    fillSelect('filter-brand', data.brands, 'All Brands');
    fillSelect('category-select', data.categories, 'All Categories');
  } catch (e) { console.error(e); }
}

function fillSelect(id, items, placeholder) {
  const el = document.getElementById(id);
  if (!el) return;
  const current = el.value;
  el.innerHTML = `<option value="">${placeholder}</option>`;
  (items || []).forEach(v => {
    const o = document.createElement('option');
    o.value = v; o.textContent = v;
    el.appendChild(o);
  });
  el.value = current;
}

async function loadProducts() {
  const params = buildQueryParams();
  try {
    const res = await fetch(`/api/products?${params}`);
    const json = await res.json();
    if (json.status !== 'success') return;
    state.page = json.page;
    state.totalPages = json.pages;
    renderProducts(json.data, json.total);
    document.getElementById('page-info').textContent = `Page ${json.page} of ${json.pages}`;
  } catch (e) { console.error(e); }
}

function buildQueryParams() {
  const p = new URLSearchParams({ page: state.page, limit: state.limit });
  const q = document.getElementById('table-search')?.value.trim();
  const brand = document.getElementById('filter-brand')?.value;
  const price = document.getElementById('filter-price')?.value;
  const rating = document.getElementById('filter-rating')?.value;
  const sort = document.getElementById('filter-sort')?.value || 'created_at';

  if (q) p.set('q', q);
  if (brand) p.set('brand', brand);
  if (rating) p.set('min_rating', rating);
  if (price) {
    const [min, max] = price.split('-').map(Number);
    if (!isNaN(min)) p.set('min_price', min);
    if (!isNaN(max)) p.set('max_price', max);
  }
  p.set('sort', sort === 'popularity' ? 'reviews' : sort);
  p.set('order', sort === 'price' ? 'asc' : 'desc');
  return p;
}

function renderProducts(products, total) {
  const tbody = document.getElementById('products-tbody');
  const countEl = document.getElementById('table-count');
  if (!tbody) return;
  countEl.textContent = `(${total || 0})`;
  tbody.innerHTML = '';

  if (!products?.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="text-center py-4 text-muted">No products found. Use the search bar to scrape.</td></tr>`;
    return;
  }

  products.forEach((p, i) => {
    const idx = (state.page - 1) * state.limit + i + 1;
    const stars = '★'.repeat(Math.round(p.rating || 0)) + '☆'.repeat(5 - Math.round(p.rating || 0));
    const img = p.product_image_url || 'https://via.placeholder.com/44';
    tbody.innerHTML += `
      <tr>
        <td>${idx}</td>
        <td><img src="${esc(img)}" class="product-thumb" alt="" onerror="this.src='https://via.placeholder.com/44'" /></td>
        <td>${esc(p.product_name)}</td>
        <td>${esc(p.brand_name)}</td>
        <td class="price-current">₹${fmt(p.current_price)}</td>
        <td class="price-original">₹${fmt(p.original_price)}</td>
        <td class="discount-badge">${Math.round(p.discount_percentage || 0)}% OFF</td>
        <td><span class="rating-stars">${stars}</span> ${(p.rating || 0).toFixed(1)}</td>
        <td>${fmtReviews(p.total_reviews)}</td>
        <td><a href="${esc(p.product_url)}" target="_blank" class="btn-link-product">View Product</a></td>
        <td><button class="btn-fav" onclick="this.classList.toggle('active')"><i class="fa-regular fa-heart"></i></button></td>
      </tr>`;
  });
}

/* ─── CHARTS ─── */
async function loadCharts(overrideProducts) {
  try {
    let chartData;
    if (overrideProducts?.length) {
      const res = await fetch('/api/charts');
      const base = await res.json();
      chartData = buildChartsFromProducts(overrideProducts, base.data?.sentiment_distribution);
    } else {
      const res = await fetch('/api/charts');
      const json = await res.json();
      chartData = json.data;
    }
    if (!chartData) return;
    renderCharts(chartData);
  } catch (e) { console.error(e); }
}

function buildChartsFromProducts(products, sentiment) {
  const brands = {}, brandPrices = {}, prices = { '₹0-500': 0, '₹500-1K': 0, '₹1K-2K': 0, '₹2K-5K': 0, '₹5K+': 0 };
  const ratings = [0, 0, 0, 0, 0];
  products.forEach(p => {
    const pr = p.current_price || 0;
    if (pr <= 500) prices['₹0-500']++;
    else if (pr <= 1000) prices['₹500-1K']++;
    else if (pr <= 2000) prices['₹1K-2K']++;
    else if (pr <= 5000) prices['₹2K-5K']++;
    else prices['₹5K+']++;
    const b = p.brand_name || 'Other';
    brands[b] = (brands[b] || 0) + 1;
    (brandPrices[b] = brandPrices[b] || []).push(pr);
    const r = Math.round(p.rating || 0);
    if (r >= 1 && r <= 5) ratings[r - 1]++;
  });
  const topBrands = Object.entries(brands).sort((a, b) => b[1] - a[1]).slice(0, 8);
  return {
    price_distribution: { labels: Object.keys(prices), values: Object.values(prices) },
    top_brands: { labels: topBrands.map(b => b[0]), values: topBrands.map(b => b[1]) },
    avg_price_by_brand: topBrands.slice(0, 6).map(([b]) => ({
      brand: b,
      avg_price: Math.round((brandPrices[b].reduce((a, c) => a + c, 0) / brandPrices[b].length)),
    })),
    rating_distribution: { labels: ['1★', '2★', '3★', '4★', '5★'], values: ratings },
    sentiment_distribution: sentiment || { labels: ['Positive', 'Neutral', 'Negative'], values: [0, 0, 0] },
  };
}

function renderCharts(data) {
  const colors = ['#a855f7', '#3b82f6', '#22c55e', '#eab308', '#ef4444', '#06b6d4', '#f97316', '#ec4899'];
  const opts = { responsive: true, maintainAspectRatio: true, plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } } };

  destroyChart('chartPrice');
  state.charts.price = new Chart(document.getElementById('chartPrice'), {
    type: 'bar',
    data: {
      labels: data.price_distribution.labels,
      datasets: [{ data: data.price_distribution.values, backgroundColor: '#a855f7', borderRadius: 6 }],
    },
    options: { ...opts, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#64748b' } }, y: { ticks: { color: '#64748b' }, beginAtZero: true } } },
  });

  destroyChart('chartBrands');
  state.charts.brands = new Chart(document.getElementById('chartBrands'), {
    type: 'doughnut',
    data: {
      labels: data.top_brands.labels,
      datasets: [{ data: data.top_brands.values, backgroundColor: colors }],
    },
    options: opts,
  });

  destroyChart('chartAvgBrand');
  const avgData = data.avg_price_by_brand || [];
  state.charts.avgBrand = new Chart(document.getElementById('chartAvgBrand'), {
    type: 'bar',
    data: {
      labels: avgData.map(d => d.brand),
      datasets: [{ data: avgData.map(d => d.avg_price), backgroundColor: '#ec4899', borderRadius: 6 }],
    },
    options: {
      indexAxis: 'y',
      ...opts,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: '#64748b' } }, y: { ticks: { color: '#64748b', font: { size: 10 } } } },
    },
  });

  destroyChart('chartRating');
  state.charts.rating = new Chart(document.getElementById('chartRating'), {
    type: 'bar',
    data: {
      labels: data.rating_distribution.labels,
      datasets: [{ data: data.rating_distribution.values, backgroundColor: '#3b82f6', borderRadius: 6 }],
    },
    options: { ...opts, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#64748b' } }, y: { ticks: { color: '#64748b' }, beginAtZero: true } } },
  });

  destroyChart('chartSentiment');
  const sent = data.sentiment_distribution;
  state.charts.sentiment = new Chart(document.getElementById('chartSentiment'), {
    type: 'pie',
    data: {
      labels: sent.labels,
      datasets: [{ data: sent.values, backgroundColor: ['#22c55e', '#94a3b8', '#ef4444'] }],
    },
    options: opts,
  });
}

function destroyChart(key) {
  const map = { chartPrice: 'price', chartBrands: 'brands', chartAvgBrand: 'avgBrand', chartRating: 'rating', chartSentiment: 'sentiment' };
  if (state.charts[map[key]]) { state.charts[map[key]].destroy(); delete state.charts[map[key]]; }
}

/* ─── FILTERS & PAGINATION ─── */
function initFilters() {
  ['filter-brand', 'filter-price', 'filter-rating', 'filter-sort'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => { state.page = 1; loadProducts(); });
  });
  document.getElementById('table-search')?.addEventListener('input', debounce(() => { state.page = 1; loadProducts(); }, 400));
  document.getElementById('btn-clear-filters')?.addEventListener('click', () => {
    ['filter-brand', 'filter-price', 'filter-rating', 'filter-sort', 'table-search'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = id === 'filter-sort' ? 'created_at' : '';
    });
    state.page = 1;
    loadProducts();
  });
}

function initPagination() {
  document.getElementById('btn-prev')?.addEventListener('click', () => {
    if (state.page > 1) { state.page--; loadProducts(); }
  });
  document.getElementById('btn-next')?.addEventListener('click', () => {
    if (state.page < state.totalPages) { state.page++; loadProducts(); }
  });
}

/* ─── EXTRA VIEWS ─── */
async function loadAnalyticsView() {
  try {
    const [aRes, wRes] = await Promise.all([fetch('/api/analytics'), fetch('/api/wordcloud')]);
    const analytics = await aRes.json();
    const wordcloud = await wRes.json();
    const tbody = document.getElementById('analytics-tbody');
    tbody.innerHTML = '';
    (analytics.data || []).slice(0, 20).forEach(item => {
      const s = item.sentiment_distribution || {};
      const pos = s.Positive || s.positive || 0;
      const neg = s.Negative || s.negative || 0;
      const neu = s.Neutral || s.neutral || 0;
      tbody.innerHTML += `<tr><td>${esc(item.product_name)}</td><td>${item.total_reviews}</td><td>${(item.avg_rating||0).toFixed(1)}</td><td>${pos}</td><td>${neg}</td><td>${neu}</td></tr>`;
    });
    const wc = document.getElementById('wordcloud-container');
    if (wordcloud.data) wc.innerHTML = `<img src="${wordcloud.data}" alt="Word Cloud" />`;
  } catch (e) { console.error(e); }
}

async function loadRecommendations() {
  try {
    const res = await fetch('/api/recommendations');
    const { data } = await res.json();
    const grid = document.getElementById('recommendations-grid');
    grid.innerHTML = '';
    if (!data?.length) {
      grid.innerHTML = '<div class="col-12 text-muted">Scrape more products to get recommendations.</div>';
      return;
    }
    data.forEach(p => {
      grid.innerHTML += `<div class="col-md-6 col-lg-4"><div class="rec-card glass-card">
        <h6>${esc(p.product_name)}</h6>
        <p class="text-muted mb-1">${esc(p.brand_name)} — ₹${fmt(p.current_price)}</p>
        <p class="mb-0">Rating: ${(p.avg_rating||0).toFixed(1)}/5 · ${p.total_reviews||0} reviews</p>
        <p class="rec-score mb-0">Score: ${p.recommendation_score || '—'}</p>
      </div></div>`;
    });
  } catch (e) { console.error(e); }
}

async function loadMongoStats() {
  try {
    const res = await fetch('/api/mongodb/stats');
    const { data } = await res.json();
    document.getElementById('mongo-stats').innerHTML = `
      <div class="mongo-stat"><span>Database</span><h3>${esc(data.database)}</h3></div>
      <div class="mongo-stat"><span>Products</span><h3>${data.products}</h3></div>
      <div class="mongo-stat"><span>Reviews</span><h3>${data.reviews}</h3></div>
      <div class="mongo-stat"><span>Analytics</span><h3>${data.analytics}</h3></div>`;
  } catch (e) { console.error(e); }
}

async function loadLogs() {
  try {
    const res = await fetch('/api/logs');
    const { data } = await res.json();
    document.getElementById('logs-content').textContent = (data || []).join('\n') || 'No logs available.';
  } catch (e) { console.error(e); }
}

function loadSettings() {
  document.getElementById('settings-db').textContent = 'myntra_data';
}

/* ─── UTILITIES ─── */
function initDarkMode() {
  document.getElementById('darkModeToggle')?.addEventListener('change', e => {
    document.documentElement.setAttribute('data-theme', e.target.checked ? 'dark' : 'light');
  });
}

function initSidebarToggle() {
  document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
    document.getElementById('sidebar')?.classList.toggle('open');
  });
}

function initExportButtons() {
  document.getElementById('btn-save-mongo')?.addEventListener('click', () => {
    showAlert('Products are automatically saved to MongoDB during scraping.', 'success');
  });
}

function showAlert(msg, type = 'info') {
  const box = document.getElementById('alert-box');
  if (!box) return;
  box.textContent = msg;
  box.className = `alert-box ${type}`;
  setTimeout(() => box.classList.add('hidden'), 5000);
  box.classList.remove('hidden');
}

function showLoader(show, text) {
  const el = document.getElementById('loading-overlay');
  if (!el) return;
  if (show) {
    document.getElementById('loading-text').textContent = text || 'Loading...';
    el.classList.remove('hidden');
  } else {
    el.classList.add('hidden');
  }
}

function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function fmt(n) { return Math.round(n || 0).toLocaleString('en-IN'); }
function fmtReviews(n) {
  n = n || 0;
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return n;
}
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
