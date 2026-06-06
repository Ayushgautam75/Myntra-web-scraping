// Dashboard JavaScript Functions
let currentPage = 1;
let currentReviewPage = 1;
let totalProductPages = 1;
let totalReviewPages = 1;
const itemsPerPage = 10;
let allProducts = [];
let lastScrapedProducts = [];
let chartInstances = {};

document.addEventListener('DOMContentLoaded', function () {
    initializeMenuItems();
    initializeRouteSection();
    setupSearchForm();
    setupProductFilters();
    loadDashboardStats();
    loadProductFilters();
    loadProducts();
    setupCharts().then(() => updateChartsWithNewData());
});

function initializeRouteSection() {
    const path = window.location.pathname.replace(/^\//, '') || 'dashboard';
    const section = ['dashboard', 'products', 'reviews', 'analytics', 'recommendations'].includes(path)
        ? path
        : 'dashboard';
    const menuItem = document.querySelector(`[data-section="${section}"]`);
    if (menuItem) {
        menuItem.click();
    }
}

function initializeMenuItems() {
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
            this.classList.add('active');
            const section = this.getAttribute('data-section');
            showSection(section);
            const newPath = section === 'dashboard' ? '/dashboard' : `/${section}`;
            if (window.location.pathname !== newPath && window.location.pathname !== '/') {
                history.replaceState(null, '', newPath);
            }
        });
    });
}

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(section => section.classList.remove('active'));
    const selectedSection = document.getElementById(`${sectionId}-section`);
    if (!selectedSection) return;

    selectedSection.classList.add('active');
    document.getElementById('section-title').textContent =
        sectionId.charAt(0).toUpperCase() + sectionId.slice(1);

    if (sectionId === 'reviews') loadReviews(1);
    else if (sectionId === 'analytics') loadAnalytics();
    else if (sectionId === 'recommendations') loadRecommendations();
    else if (sectionId === 'products') loadProducts(currentPage);
    else if (sectionId === 'dashboard') {
        loadDashboardStats();
        updateChartsWithNewData();
    }
}

async function loadDashboardStats() {
    try {
        const response = await fetch('/api/dashboard-stats');
        const data = await response.json();
        if (data.status !== 'success') {
            showAlert(data.message || 'Could not load dashboard stats.', 'error');
            return;
        }

        const stats = data.data;
        document.getElementById('total-products').textContent = stats.total_products || 0;
        document.getElementById('avg-rating').textContent =
            stats.avg_rating ? `${Number(stats.avg_rating).toFixed(1)}/5` : '0/5';
        document.getElementById('product-count').textContent = stats.total_products || 0;
        document.getElementById('brands-found').textContent = stats.brands_found || 0;
        document.getElementById('avg-price').textContent =
            `₹${Math.round(stats.avg_price || 0).toLocaleString()}`;

        document.getElementById('last-updated').textContent =
            new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
        showAlert('Unable to load dashboard statistics.', 'error');
    }
}

function buildProductQueryParams(page = 1) {
    const params = new URLSearchParams({
        page: page,
        limit: itemsPerPage,
        sort: document.getElementById('sort-field')?.value || 'created_at',
        order: document.getElementById('sort-order')?.value || 'desc',
    });

    const search = document.getElementById('product-search')?.value.trim();
    const brand = document.getElementById('brand-filter')?.value;
    const category = document.getElementById('category-filter')?.value;
    const maxPrice = document.getElementById('price-range')?.value;

    if (search) params.set('q', search);
    if (brand) params.set('brand', brand);
    if (category) params.set('category', category);
    if (maxPrice) params.set('max_price', maxPrice);
    return params;
}

async function loadProducts(page = 1) {
    try {
        const params = buildProductQueryParams(page);
        const response = await fetch(`/api/products?${params.toString()}`);
        const data = await response.json();

        if (data.status === 'success') {
            allProducts = data.data;
            renderProductsTable(data.data);
            currentPage = data.page || page;
            totalProductPages = data.pages || 1;
            const pageInfo = document.getElementById('page-info');
            if (pageInfo) pageInfo.textContent = `Page ${currentPage} of ${totalProductPages}`;
        } else {
            showAlert(data.message || 'Could not load products.', 'error');
        }
    } catch (error) {
        console.error('Error loading products:', error);
        showAlert('Unable to load products.', 'error');
    }
}

async function loadProductFilters() {
    try {
        const response = await fetch('/api/products/filters');
        const data = await response.json();
        if (data.status !== 'success') return;

        const brandFilter = document.getElementById('brand-filter');
        const categoryFilter = document.getElementById('category-filter');
        if (!brandFilter || !categoryFilter) return;

        data.data.brands.forEach(brand => {
            const option = document.createElement('option');
            option.value = brand;
            option.textContent = brand;
            brandFilter.appendChild(option);
        });

        data.data.categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            categoryFilter.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading filters:', error);
    }
}

function setupProductFilters() {
    const priceRange = document.getElementById('price-range');
    if (priceRange) {
        priceRange.addEventListener('input', function () {
            document.getElementById('price-value').textContent =
                `₹${Number(this.value).toLocaleString()}`;
        });
    }

    const productSearch = document.getElementById('product-search');
    if (productSearch) {
        productSearch.addEventListener('keyup', debounce(() => loadProducts(1), 400));
    }

    ['sort-field', 'sort-order', 'brand-filter', 'category-filter'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => loadProducts(1));
    });
}

function applyProductFilters() {
    loadProducts(1);
}

function renderProductsTable(products) {
    const tbody = document.getElementById('products-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!products.length) {
        tbody.innerHTML =
            '<tr><td colspan="8" style="text-align:center;padding:20px;">No products found. Search and scrape products first!</td></tr>';
        return;
    }

    products.forEach(product => {
        const row = document.createElement('tr');
        const stars = '⭐'.repeat(Math.round(product.rating || 0));
        const image = product.product_image_url || 'https://via.placeholder.com/40';
        row.innerHTML = `
            <td><img src="${image}" alt="Product" class="product-image" style="width:40px;height:40px;object-fit:cover;border-radius:4px;"></td>
            <td>${escapeHtml(product.product_name)}</td>
            <td>${escapeHtml(product.brand_name)}</td>
            <td>₹${Math.round(product.current_price || 0).toLocaleString()}</td>
            <td>${Math.round(product.discount_percentage || 0)}%</td>
            <td><span style="color:#f59e0b;">${stars || '—'}</span></td>
            <td>${product.total_reviews || 0}</td>
            <td>
                <a href="${product.product_url}" target="_blank" rel="noopener" class="btn-view">View</a>
            </td>`;
        tbody.appendChild(row);
    });
}

async function loadReviews(page = 1) {
    try {
        const params = new URLSearchParams({ page, limit: 20 });
        const sentiment = document.getElementById('sentiment-filter')?.value;
        const minRating = document.getElementById('review-rating-filter')?.value;
        if (sentiment) params.set('sentiment', sentiment);
        if (minRating) params.set('min_rating', minRating);

        const response = await fetch(`/api/reviews?${params.toString()}`);
        const data = await response.json();

        if (data.status === 'success') {
            renderReviews(data.data);
            currentReviewPage = data.page || page;
            totalReviewPages = data.pages || 1;
            const pageInfo = document.getElementById('review-page-info');
            if (pageInfo) pageInfo.textContent = `Page ${currentReviewPage} of ${totalReviewPages}`;
            if (data.message && !data.data.length) showAlert(data.message, 'info');
        } else {
            showAlert(data.message || 'Could not load reviews.', 'error');
        }
    } catch (error) {
        console.error('Error loading reviews:', error);
        showAlert('Unable to load reviews.', 'error');
    }
}

function renderReviews(reviews) {
    const reviewsList = document.getElementById('reviews-list');
    if (!reviewsList) return;
    reviewsList.innerHTML = '';

    if (!reviews.length) {
        reviewsList.innerHTML =
            '<p style="text-align:center;padding:20px;">No reviews found for the selected filters.</p>';
        return;
    }

    reviews.forEach(review => {
        const sentimentColor =
            review.sentiment === 'Positive' ? '#10b981' :
            review.sentiment === 'Negative' ? '#ef4444' : '#9ca3af';

        const card = document.createElement('div');
        card.className = 'review-card';
        card.innerHTML = `
            <div class="review-header">
                <span class="review-user">${escapeHtml(review.user_name)}</span>
                <span class="review-rating">${'⭐'.repeat(review.user_rating || 0)}</span>
            </div>
            ${review.product_name ? `<p class="review-product"><strong>Product:</strong> ${escapeHtml(review.product_name)}</p>` : ''}
            <p class="review-text">"${escapeHtml(review.review_text)}"</p>
            <div class="review-meta">
                <span>📅 ${escapeHtml(review.review_date)}</span>
                <span style="color:${sentimentColor};font-weight:bold;">
                    ${review.sentiment} (${Number(review.sentiment_score || 0).toFixed(2)})
                </span>
            </div>`;
        reviewsList.appendChild(card);
    });
}

async function loadAnalytics() {
    try {
        const response = await fetch('/api/analytics');
        const data = await response.json();
        if (data.status === 'success') renderAnalyticsTable(data.data);
        else showAlert(data.message || 'Could not load analytics.', 'error');
    } catch (error) {
        console.error('Error loading analytics:', error);
        showAlert('Unable to load analytics.', 'error');
    }
}

function renderAnalyticsTable(analytics) {
    const tbody = document.getElementById('analytics-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!analytics.length) {
        tbody.innerHTML =
            '<tr><td colspan="7" style="text-align:center;padding:20px;">No analytics data yet.</td></tr>';
        return;
    }

    analytics.slice(0, 20).forEach(item => {
        const sentiment = item.sentiment_distribution || {};
        const positive = sentiment.Positive || sentiment.positive || 0;
        const negative = sentiment.Negative || sentiment.negative || 0;
        const neutral = sentiment.Neutral || sentiment.neutral || 0;
        const total = positive + negative + neutral;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${new Date(item.scrape_timestamp || item.timestamp).toLocaleDateString()}</td>
            <td>${escapeHtml(item.product_name)}</td>
            <td>${item.total_reviews}</td>
            <td>${Number(item.avg_rating || 0).toFixed(2)}</td>
            <td>${total ? ((positive / total) * 100).toFixed(1) : 0}%</td>
            <td>${total ? ((negative / total) * 100).toFixed(1) : 0}%</td>
            <td>${total ? ((neutral / total) * 100).toFixed(1) : 0}%</td>`;
        tbody.appendChild(row);
    });
}

async function loadRecommendations() {
    try {
        const response = await fetch('/api/products?page=1&limit=100&sort=rating&order=desc');
        const data = await response.json();
        if (data.status === 'success') {
            const recommended = data.data.filter(p =>
                (p.rating || 0) >= 4.0 && (p.total_reviews || 0) >= 5
            );
            renderRecommendations(recommended);
        }
    } catch (error) {
        console.error('Error loading recommendations:', error);
    }
}

function renderRecommendations(recommendations) {
    const recList = document.getElementById('recommendations-list');
    if (!recList) return;
    recList.innerHTML = '';

    if (!recommendations.length) {
        recList.innerHTML =
            '<p style="text-align:center;padding:20px;">No recommendations yet. Scrape more products!</p>';
        return;
    }

    recommendations.slice(0, 12).forEach(product => {
        const score = (
            ((product.rating || 0) / 5) * 40 +
            Math.min(((product.total_reviews || 0) / 500) * 30, 30) +
            30
        ).toFixed(1);

        const card = document.createElement('div');
        card.className = 'recommendation-card';
        card.innerHTML = `
            <h4>${escapeHtml(product.product_name)}</h4>
            <p><strong>Brand:</strong> ${escapeHtml(product.brand_name)}</p>
            <p><strong>Price:</strong> ₹${Math.round(product.current_price || 0).toLocaleString()}</p>
            <p><strong>Category:</strong> ${escapeHtml(product.product_category)}</p>
            <div class="recommendation-score">
                <div class="score-item"><span class="score-label">Rating</span><span class="score-value">${Number(product.rating || 0).toFixed(1)}/5</span></div>
                <div class="score-item"><span class="score-label">Reviews</span><span class="score-value">${product.total_reviews || 0}</span></div>
                <div class="score-item"><span class="score-label">Score</span><span class="score-value">${score}</span></div>
            </div>`;
        recList.appendChild(card);
    });
}

async function setupCharts() {
    chartInstances.price = createBarChart('priceChart', ['₹0-500', '₹500-1k', '₹1k-2k', '₹2k+'], '#ff5722');
    chartInstances.rating = createBarChart('ratingChart', ['1⭐', '2⭐', '3⭐', '4⭐', '5⭐'], '#3b82f6');

    const sentimentCtx = document.getElementById('sentimentChart');
    if (sentimentCtx) {
        chartInstances.sentiment = new Chart(sentimentCtx, {
            type: 'doughnut',
            data: {
                labels: ['Positive', 'Negative', 'Neutral'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#10b981', '#ef4444', '#9ca3af'],
                    borderColor: '#1f2937',
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom', labels: { color: '#e5e7eb' } } },
            },
        });
    }

    const brandCtx = document.getElementById('brandChart');
    if (brandCtx) {
        chartInstances.brand = new Chart(brandCtx, {
            type: 'bar',
            data: { labels: [], datasets: [{ label: 'Products', data: [], backgroundColor: '#f59e0b' }] },
            options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } },
        });
    }
}

function createBarChart(canvasId, labels, color) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ label: 'Products', data: labels.map(() => 0), backgroundColor: color }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } },
        },
    });
}

function setupSearchForm() {
    const searchForm = document.getElementById('search-form');
    const searchBox = document.getElementById('search-box');
    const urlBox = document.getElementById('product-url-box');
    const countInput = document.getElementById('product-count');
    if (!searchForm) return;

    if (countInput) {
        countInput.addEventListener('change', () => clampProductCount(countInput));
    }

    searchForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        const query = searchBox?.value.trim() || '';
        const productUrl = urlBox?.value.trim() || '';
        const productCount = getProductCount();

        if (!query && !productUrl) {
            showAlert('Enter a product name or paste a Myntra product URL.', 'warning');
            return;
        }

        if (productUrl) {
            const validation = validateMyntraUrl(productUrl);
            if (!validation.valid) {
                showAlert(validation.message, 'error');
                return;
            }
            await scrapeProducts({ productUrl: validation.url, productCount: 1, mode: 'url' });
            return;
        }

        await scrapeProducts({ query, productCount, mode: 'name' });
    });
}

function getProductCount() {
    const countInput = document.getElementById('product-count');
    return clampProductCount(countInput);
}

function clampProductCount(input) {
    if (!input) return 3;
    let value = parseInt(input.value, 10);
    if (Number.isNaN(value)) value = 3;
    value = Math.min(50, Math.max(1, value));
    input.value = value;
    return value;
}

function validateMyntraUrl(input) {
    let url = input.trim();
    if (url.toLowerCase().startsWith('www.')) {
        url = 'https://' + url;
    } else if (!/^https?:\/\//i.test(url)) {
        url = 'https://' + url;
    }

    try {
        const parsed = new URL(url);
        if (!parsed.hostname.toLowerCase().includes('myntra.com')) {
            return { valid: false, message: 'Invalid URL. Please paste a myntra.com product link.' };
        }
        if (!parsed.pathname || parsed.pathname === '/') {
            return { valid: false, message: 'Invalid product URL. Use a direct Myntra product page link.' };
        }
        return { valid: true, url: parsed.origin + parsed.pathname };
    } catch {
        return { valid: false, message: 'Invalid URL format. Example: https://www.myntra.com/...' };
    }
}

async function scrapeProducts({ query, productUrl, productCount, mode }) {
    const isUrlMode = mode === 'url';

    try {
        const loadingText = isUrlMode
            ? 'Scraping product from URL...\nExtracting details, reviews & sentiment...'
            : `Searching Myntra for "${query}"...\nScraping ${productCount} product(s). This may take a few minutes.`;
        showLoadingOverlay(true, loadingText);

        const payload = {
            product_count: productCount,
        };
        if (isUrlMode) {
            payload.product_url = productUrl;
        } else {
            payload.query = query;
        }

        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        let data;
        try {
            data = await response.json();
        } catch {
            showLoadingOverlay(false);
            showAlert('Network error. Could not read server response.', 'error');
            return;
        }

        showLoadingOverlay(false);

        if (response.ok && data.status === 'success') {
            lastScrapedProducts = data.data || [];
            const requested = data.requested_count || productCount;
            showAlert(
                `Success! Scraped ${data.scraped_count} of ${requested} requested product(s).`,
                'success'
            );

            document.getElementById('search-box').value = '';
            document.getElementById('product-url-box').value = '';

            await loadDashboardStats();
            await loadProductFilters();
            renderProductsTable(lastScrapedProducts);
            document.getElementById('page-info').textContent =
                `Showing ${lastScrapedProducts.length} scraped product(s)`;
            await updateChartsFromProducts(lastScrapedProducts);
            document.querySelector('[data-section="products"]')?.click();
        } else {
            showAlert(data.message || 'Scraping failed. Please try again.', 'error');
        }
    } catch {
        showLoadingOverlay(false);
        showAlert('Network error while scraping. Please check your connection.', 'error');
    }
}

async function updateChartsFromProducts(products) {
    if (!products.length) {
        await updateChartsWithNewData();
        return;
    }
    updatePriceChart(products);
    updateBrandChart(products);
    updateRatingChart(products);
    await updateSentimentChart();
}

function showLoadingOverlay(show, text = 'Loading...') {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) return;
    const loadingText = document.getElementById('loading-text');
    if (show) {
        if (loadingText) loadingText.innerHTML = text.replace(/\n/g, '<br>');
        overlay.classList.remove('hidden');
        overlay.style.display = 'flex';
    } else {
        overlay.classList.add('hidden');
        overlay.style.display = 'none';
    }
}

function showAlert(message, type = 'info') {
    const alertDiv = document.getElementById('alert-message');
    if (!alertDiv) return;
    alertDiv.textContent = message;
    alertDiv.className = `alert-message ${type}`;
    alertDiv.classList.remove('hidden');
    setTimeout(() => alertDiv.classList.add('hidden'), 6000);
}

async function updateChartsWithNewData() {
    try {
        const response = await fetch('/api/products?page=1&limit=200');
        const data = await response.json();
        if (data.status === 'success' && data.data.length) {
            updatePriceChart(data.data);
            updateBrandChart(data.data);
            updateRatingChart(data.data);
            await updateSentimentChart();
        }
    } catch (error) {
        console.error('Error updating charts:', error);
    }
}

function updatePriceChart(products) {
    const ranges = { '₹0-500': 0, '₹500-1k': 0, '₹1k-2k': 0, '₹2k+': 0 };
    products.forEach(p => {
        const price = p.current_price || 0;
        if (price <= 500) ranges['₹0-500']++;
        else if (price <= 1000) ranges['₹500-1k']++;
        else if (price <= 2000) ranges['₹1k-2k']++;
        else ranges['₹2k+']++;
    });
    if (chartInstances.price) {
        chartInstances.price.data.datasets[0].data = Object.values(ranges);
        chartInstances.price.update();
    }
}

function updateRatingChart(products) {
    const ratings = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    products.forEach(p => {
        const rating = Math.min(5, Math.max(1, Math.round(p.rating || 0)));
        if (p.rating) ratings[rating]++;
    });
    if (chartInstances.rating) {
        chartInstances.rating.data.datasets[0].data = Object.values(ratings);
        chartInstances.rating.update();
    }
}

function updateBrandChart(products) {
    const brands = {};
    products.forEach(p => {
        const brand = p.brand_name || 'Other';
        brands[brand] = (brands[brand] || 0) + 1;
    });
    const topBrands = Object.entries(brands).sort((a, b) => b[1] - a[1]).slice(0, 8);
    if (chartInstances.brand) {
        chartInstances.brand.data.labels = topBrands.map(([k]) => k);
        chartInstances.brand.data.datasets[0].data = topBrands.map(([, v]) => v);
        chartInstances.brand.update();
    }
}

async function updateSentimentChart() {
    try {
        const response = await fetch('/api/dashboard-stats');
        const data = await response.json();
        if (data.status !== 'success' || !chartInstances.sentiment) return;

        const sentimentData = {};
        (data.data.sentiment_distribution || []).forEach(item => {
            sentimentData[item._id] = item.count;
        });
        chartInstances.sentiment.data.datasets[0].data = [
            sentimentData.Positive || 0,
            sentimentData.Negative || 0,
            sentimentData.Neutral || 0,
        ];
        chartInstances.sentiment.update();
    } catch (error) {
        console.error('Error updating sentiment chart:', error);
    }
}

function nextPage() {
    if (currentPage < totalProductPages) loadProducts(currentPage + 1);
}

function prevPage() {
    if (currentPage > 1) loadProducts(currentPage - 1);
}

function nextReviewPage() {
    if (currentReviewPage < totalReviewPages) loadReviews(currentReviewPage + 1);
}

function prevReviewPage() {
    if (currentReviewPage > 1) loadReviews(currentReviewPage - 1);
}

function clearFilters() {
    ['brand-filter', 'category-filter', 'product-search'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const priceRange = document.getElementById('price-range');
    if (priceRange) {
        priceRange.value = 50000;
        document.getElementById('price-value').textContent = '₹50000';
    }
    loadProducts(1);
}

function exportToExcel() {
    showAlert('Use CSV export for now. Excel export uses the same data format.', 'info');
}

function exportToJSON() {
    fetch('/api/products?page=1&limit=500')
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') throw new Error('Export failed');
            const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'products.json';
            a.click();
            URL.revokeObjectURL(url);
        })
        .catch(() => showAlert('Could not export JSON.', 'error'));
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}
