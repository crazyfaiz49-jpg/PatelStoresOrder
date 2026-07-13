const STORAGE_KEY = 'patel-stores-cart';
const ORDERS_KEY = 'patel-stores-orders';
const LOGIN_KEY = 'patel-stores-auth';
const USER_KEY = 'patel-stores-user';
const LOGIN_API = 'https://script.google.com/macros/s/AKfycbzXLQEuY6Vj0Ufs4gOmVJ0YoB4X4bN5XKkkxVjTU4rBP0a0ntrQQp2TLSRAERsqVDw/exec';
const DB_NAME = 'patel-stores-db';
const DB_VERSION = 1;
const PRODUCTS_STORE = 'products';
const ORDERS_STORE = 'orders';
const SYNCED_ORDERS_KEY = 'patel-stores-synced-orders';

const state = {
  products: [],
  filteredProducts: [],
  activeCategory: 'All',
  searchTerm: '',
  cart: JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'),
  user: null,
  pendingOrderCount: 0,
  searchDebounce: null,
  modalProductId: null,
  modalImageIndex: 0,
  viewer: {
    open: false,
    images: [],
    index: 0,
    scale: 1,
    x: 0,
    y: 0,
    dragging: false,
    dragStartX: 0,
    dragStartY: 0,
    startX: 0,
    startY: 0,
    touchStartX: 0,
    touchStartY: 0,
    swipeDown: 0,
    baseScale: 1,
    pinchDistance: 0
  }
};

const elements = {
  welcomePill: document.getElementById('welcome-pill'),
  logoutBtn: document.getElementById('logout-btn'),
  shopName: document.getElementById('shop-name'),
  mobileNumber: document.getElementById('mobile-number'),
  menuProfile: document.getElementById('menu-profile'),
  appShell: document.getElementById('app-shell'),
  loginScreen: document.getElementById('login-screen'),
  loginForm: document.getElementById('login-form'),
  loginMobile: document.getElementById('login-mobile'),
  loginError: document.getElementById('login-error'),
  search: document.getElementById('search'),
  products: document.getElementById('products'),
  resultsCount: document.getElementById('results-count'),
  categoryCards: document.getElementById('category-cards'),
  menuCategoryCards: document.getElementById('menu-category-cards'),
  cartCount: document.getElementById('cart-count'),
  cartTotalItems: document.getElementById('cart-total-items'),
  cartItems: document.getElementById('cart-items'),
  cartToggle: document.getElementById('cart-toggle'),
  stickyItems: document.getElementById('sticky-items'),
  stickyTotal: document.getElementById('sticky-total'),
  stickyCheckout: document.getElementById('sticky-checkout'),
  closeCart: document.getElementById('close-cart'),
  menuToggle: document.getElementById('menu-toggle'),
  closeMenu: document.getElementById('close-menu'),
  syncStatus: document.getElementById('sync-status'),
  syncPanel: document.getElementById('sync-panel'),
  syncSummary: document.getElementById('sync-summary'),
  retrySync: document.getElementById('retry-sync'),
  drawerOverlay: document.getElementById('drawer-overlay'),
  menuDrawer: document.getElementById('menu-drawer'),
  cartDrawer: document.getElementById('cart-drawer'),
  checkoutForm: document.getElementById('checkout-form'),
  sheetEndpoint: document.getElementById('sheet-endpoint'),
  toast: document.getElementById('toast'),
  productModal: document.getElementById('product-modal'),
  productModalBackdrop: document.getElementById('product-modal-backdrop'),
  closeProductModal: document.getElementById('close-product-modal'),
  productModalName: document.getElementById('product-modal-name'),
  productModalCategory: document.getElementById('product-modal-category'),
  productModalDescription: document.getElementById('product-modal-description'),
  productModalPrice: document.getElementById('product-modal-price'),
  productModalMrp: document.getElementById('product-modal-mrp'),
  productModalStock: document.getElementById('product-modal-stock'),
  productModalImageShell: document.getElementById('product-modal-image-shell'),
  productModalThumbs: document.getElementById('product-modal-thumbs'),
  productModalPrev: document.getElementById('product-modal-prev'),
  productModalNext: document.getElementById('product-modal-next'),
  productModalQty: document.getElementById('product-modal-qty'),
  productModalPlus: document.getElementById('product-modal-plus'),
  productModalMinus: document.getElementById('product-modal-minus'),
  productModalAdd: document.getElementById('product-modal-add'),
  imageViewer: document.getElementById('image-viewer'),
  imageViewerBackdrop: document.getElementById('image-viewer-backdrop'),
  imageViewerClose: document.getElementById('image-viewer-close'),
  imageViewerPrev: document.getElementById('image-viewer-prev'),
  imageViewerNext: document.getElementById('image-viewer-next'),
  imageViewerImg: document.getElementById('image-viewer-img'),
  imageViewerShell: document.getElementById('image-viewer-shell'),
  imageViewerThumbs: document.getElementById('image-viewer-thumbs')
};

function init() {
  bindEvents();
  registerServiceWorker();
  initSyncSystem();

  const savedUser = localStorage.getItem(USER_KEY);
  if (savedUser) {
    state.user = JSON.parse(savedUser);
    showStorefront();
    updateWelcomeMessage();
    loadProducts();
    renderCart();
  } else {
    showLogin();
  }
}

function bindEvents() {
  elements.loginForm.addEventListener('submit', handleLogin);
  elements.logoutBtn.addEventListener('click', handleLogout);

  elements.search.addEventListener('input', (event) => {
    window.clearTimeout(state.searchDebounce);
    state.searchDebounce = window.setTimeout(() => {
      state.searchTerm = event.target.value.trim();
      renderProducts();
    }, 80);
  });

  elements.categoryCards.addEventListener('click', handleCategoryClick);
  elements.menuCategoryCards.addEventListener('click', handleCategoryClick);

  elements.cartToggle.addEventListener('click', () => toggleCart(true));
  elements.stickyCheckout.addEventListener('click', () => {
    toggleCart(true);
    elements.checkoutForm.scrollIntoView({ behavior: 'smooth', block: 'end' });
  });

  elements.closeCart.addEventListener('click', () => toggleCart(false));
  elements.menuToggle.addEventListener('click', () => toggleMenu(true));
  elements.closeMenu.addEventListener('click', () => toggleMenu(false));
  elements.drawerOverlay.addEventListener('click', closeAllDrawers);

  document.addEventListener('keydown', handleGlobalKeyDown);

  elements.checkoutForm.addEventListener('submit', handleCheckout);
  elements.syncStatus.addEventListener('click', toggleSyncPanel);
  elements.retrySync.addEventListener('click', () => syncPendingOrders());

  elements.closeProductModal.addEventListener('click', closeProductModal);
  elements.productModalBackdrop.addEventListener('click', closeProductModal);
  elements.productModalPrev.addEventListener('click', () => shiftProductModalImage(-1));
  elements.productModalNext.addEventListener('click', () => shiftProductModalImage(1));
  elements.productModalPlus.addEventListener('click', () => adjustModalQuantity(1));
  elements.productModalMinus.addEventListener('click', () => adjustModalQuantity(-1));
  elements.productModalAdd.addEventListener('click', addFromProductModal);

  elements.imageViewerClose.addEventListener('click', closeImageViewer);
  elements.imageViewerBackdrop.addEventListener('click', closeImageViewer);
  elements.imageViewerPrev.addEventListener('click', () => shiftViewerImage(-1));
  elements.imageViewerNext.addEventListener('click', () => shiftViewerImage(1));
  elements.imageViewerShell.addEventListener('wheel', handleViewerWheel, { passive: false });
  elements.imageViewerShell.addEventListener('mousedown', handleViewerMouseDown);
  elements.imageViewerShell.addEventListener('touchstart', handleViewerTouchStart, { passive: false });
  elements.imageViewerShell.addEventListener('touchmove', handleViewerTouchMove, { passive: false });
  elements.imageViewerShell.addEventListener('touchend', handleViewerTouchEnd, { passive: false });
  document.addEventListener('mousemove', handleViewerMouseMove);
  document.addEventListener('mouseup', handleViewerMouseUp);
}

function handleGlobalKeyDown(event) {
  if (event.key !== 'Escape') return;
  if (!elements.imageViewer.classList.contains('is-hidden')) {
    closeImageViewer();
    return;
  }
  if (!elements.productModal.classList.contains('is-hidden')) {
    closeProductModal();
    return;
  }
  closeAllDrawers();
}

function handleCategoryClick(event) {
  const button = event.target.closest('[data-category]');
  if (!button) return;
  const selected = button.dataset.category || 'All';
  state.activeCategory = selected;
  updateCategoryActiveState();
  renderProducts();

  const targetInMain = elements.categoryCards.querySelector(`[data-category="${cssEscape(selected)}"]`);
  if (targetInMain) {
    targetInMain.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }
}

function initSyncSystem() {
  updateSyncStatus();
  window.addEventListener('online', () => {
    updateSyncStatus();
    syncPendingOrders();
    showToast('Connection restored. Syncing pending orders.', 'success');
  });
  window.addEventListener('offline', () => {
    updateSyncStatus();
    showToast('Offline mode enabled. Orders will sync when connection returns.', 'info');
  });
  navigator.serviceWorker?.addEventListener('message', (event) => {
    if (event.data?.type === 'SYNC_ORDERS') {
      syncPendingOrders();
    }
  });
  syncPendingOrders();
}

function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('service-worker.js').catch((error) => {
      console.error('Service worker registration failed', error);
    });
  }
}

function toggleSyncPanel() {
  const open = elements.syncPanel.classList.contains('is-hidden');
  elements.syncPanel.classList.toggle('is-hidden', !open);
  elements.syncStatus.setAttribute('aria-expanded', String(open));
  if (open) {
    updateSyncStatus();
  }
}

function updateSyncStatus() {
  const pendingCount = state.pendingOrderCount || 0;
  const online = navigator.onLine;
  const label = online ? '● Online' : '● Offline';
  elements.syncStatus.textContent = pendingCount > 0 ? `${label} (${pendingCount})` : label;
  elements.syncStatus.style.background = online ? 'rgba(255,255,255,.16)' : 'rgba(245,158,11,.25)';

  const syncedCount = Number(localStorage.getItem(SYNCED_ORDERS_KEY) || '0');
  elements.syncSummary.textContent = online
    ? `${pendingCount} pending • ${syncedCount} synced • ready to sync`
    : `${pendingCount} pending • ${syncedCount} synced • offline`;
}

function showLogin() {
  elements.appShell.classList.add('is-hidden');
  elements.loginScreen.classList.remove('is-hidden');
  elements.welcomePill.classList.add('is-hidden');
  elements.logoutBtn.classList.add('is-hidden');
  elements.menuProfile.classList.add('is-hidden');
}

function showStorefront() {
  elements.appShell.classList.remove('is-hidden');
  elements.loginScreen.classList.add('is-hidden');
}

function updateWelcomeMessage() {
  if (state.user) {
    elements.welcomePill.textContent = `Welcome, ${state.user.shopName}`;
    elements.welcomePill.classList.remove('is-hidden');
    elements.shopName.textContent = state.user.shopName || 'Shop Name';
    elements.mobileNumber.textContent = state.user.mobile || 'Mobile Number';
    elements.menuProfile.classList.remove('is-hidden');
  } else {
    elements.welcomePill.textContent = 'Welcome';
    elements.welcomePill.classList.add('is-hidden');
    elements.shopName.textContent = 'Shop Name';
    elements.mobileNumber.textContent = 'Mobile Number';
    elements.menuProfile.classList.add('is-hidden');
  }

  elements.logoutBtn.classList.remove('is-hidden');
}

async function handleLogin(event) {
  event.preventDefault();

  const mobile = elements.loginMobile.value.trim();
  if (!/^\d{10}$/.test(mobile)) {
    elements.loginError.textContent = 'Please enter a valid 10-digit mobile number.';
    return;
  }

  const savedUser = JSON.parse(localStorage.getItem(USER_KEY) || '{}');
  if (!navigator.onLine && savedUser?.mobile === mobile) {
    const user = {
      shopName: savedUser.shopName || 'Retailer',
      mobile,
      loginToken: savedUser.loginToken || 'offline-session',
      loginTime: savedUser.loginTime || new Date().toISOString()
    };
    state.user = user;
    localStorage.setItem(LOGIN_KEY, 'true');
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    showStorefront();
    updateWelcomeMessage();
    loadProducts();
    renderCart();
    showToast('Signed in offline using saved retailer details.', 'info');
    return;
  }

  elements.loginError.textContent = '';
  elements.loginForm.querySelector('button').disabled = true;

  try {
    const response = await fetch(`${LOGIN_API}?action=login&mobile=${encodeURIComponent(mobile)}`);
    const data = await response.json();

    if (data.success === true) {
      const user = {
        shopName: data.shopName || 'Retailer',
        mobile,
        loginToken: data.loginToken || 'online-session',
        loginTime: new Date().toISOString()
      };

      state.user = user;
      localStorage.setItem(LOGIN_KEY, 'true');
      localStorage.setItem(USER_KEY, JSON.stringify(user));
      showStorefront();
      updateWelcomeMessage();
      loadProducts();
      renderCart();
    } else if (data.message === 'notfound') {
      elements.loginError.textContent = 'You are not registered with Patel Stores. Kindly contact 7863059164';
    } else if (data.message === 'inactive') {
      elements.loginError.textContent = 'Your account is inactive. Please contact Patel Stores.';
    } else {
      elements.loginError.textContent = data.message || 'Login failed. Please try again.';
    }
  } catch (error) {
    console.error(error);
    if (savedUser?.mobile === mobile) {
      const user = {
        shopName: savedUser.shopName || 'Retailer',
        mobile,
        loginToken: savedUser.loginToken || 'offline-session',
        loginTime: savedUser.loginTime || new Date().toISOString()
      };
      state.user = user;
      localStorage.setItem(LOGIN_KEY, 'true');
      localStorage.setItem(USER_KEY, JSON.stringify(user));
      showStorefront();
      updateWelcomeMessage();
      loadProducts();
      renderCart();
      showToast('Signed in offline using saved retailer details.', 'info');
    } else {
      elements.loginError.textContent = 'Unable to reach Patel Stores login service. Please try again.';
    }
  } finally {
    elements.loginForm.querySelector('button').disabled = false;
  }
}

function handleLogout() {
  localStorage.removeItem(LOGIN_KEY);
  localStorage.removeItem(USER_KEY);
  state.user = null;
  elements.loginForm.reset();
  elements.loginError.textContent = '';
  showLogin();
}

async function loadProducts() {
  try {
    const cachedProducts = (await getProductsFromDb()).map(normalizeProduct);
    if (cachedProducts.length) {
      state.products = cachedProducts;
      renderCategoryNavigation();
      renderProducts();
    }

    if (!navigator.onLine) {
      if (!cachedProducts.length) {
        elements.products.innerHTML = '<div class="empty-state">Products could not be loaded offline. Please connect to the internet once.</div>';
        elements.resultsCount.textContent = 'Unavailable';
      }
      return;
    }

    const response = await fetch('products.json');
    if (!response.ok) {
      throw new Error('Unable to load products');
    }

    const data = await response.json();
    const products = (data.products || []).map(normalizeProduct);
    state.products = products;
    await saveProductsToDb(products);
    renderCategoryNavigation();
    renderProducts();
  } catch (error) {
    elements.products.innerHTML = '<div class="empty-state">Products could not be loaded. Please refresh the page.</div>';
    elements.resultsCount.textContent = 'Unavailable';
    showToast('Unable to load products from the catalog.', 'error');
    console.error(error);
  }
}

function normalizeProduct(raw) {
  const price = Number(raw.price || 0);
  const mrpValue = Number(raw.mrp || raw.mrpPrice || raw.mrp_price || 0);
  const stockRaw = raw.stock ?? raw.availableStock ?? raw.inventory ?? null;
  const stock = Number.isFinite(Number(stockRaw)) ? Number(stockRaw) : null;

  return {
    ...raw,
    id: String(raw.id || '').trim(),
    name: String(raw.name || '').trim(),
    category: String(raw.category || 'General').trim() || 'General',
    description: String(raw.description || '').trim(),
    price: Number.isFinite(price) ? price : 0,
    mrp: Number.isFinite(mrpValue) && mrpValue > 0 ? mrpValue : null,
    stock,
    images: extractProductImages(raw),
    image: extractProductImages(raw)[0]
  };
}

function extractProductImages(product) {
  const items = [];

  if (Array.isArray(product.images)) {
    items.push(...product.images);
  } else if (typeof product.images === 'string' && product.images.trim()) {
    const source = product.images.trim();
    try {
      const parsed = JSON.parse(source);
      if (Array.isArray(parsed)) {
        items.push(...parsed);
      } else {
        items.push(source);
      }
    } catch (_) {
      source.split(/[|,]/).forEach((part) => items.push(part));
    }
  }

  if (typeof product.image === 'string' && product.image.trim()) {
    items.push(product.image.trim());
  }

  const normalized = [...new Set(items.map((src) => String(src || '').trim()).filter(Boolean))];
  return normalized.length ? normalized : ['images/placeholder.svg'];
}

function renderCategoryNavigation() {
  const counts = {};
  state.products.forEach((product) => {
    counts[product.category] = (counts[product.category] || 0) + 1;
  });

  const categories = ['All', ...Object.keys(counts).sort((a, b) => a.localeCompare(b))];

  elements.categoryCards.innerHTML = categories
    .map((category) => {
      const count = category === 'All' ? state.products.length : counts[category] || 0;
      return `
        <button class="category-card" type="button" data-category="${escapeHtml(category)}">
          <span class="category-icon">${getCategoryIcon(category)}</span>
          <span class="category-name">${escapeHtml(category)}</span>
          <span class="category-count">${count}</span>
        </button>
      `;
    })
    .join('');

  elements.menuCategoryCards.innerHTML = categories
    .map((category) => `<button class="filter-chip" data-category="${escapeHtml(category)}">${escapeHtml(category)}</button>`)
    .join('');

  updateCategoryActiveState();
}

function updateCategoryActiveState() {
  document.querySelectorAll('[data-category]').forEach((node) => {
    const isActive = node.dataset.category === state.activeCategory;
    node.classList.toggle('active', isActive);
  });
}

function renderProducts() {
  const searchLower = state.searchTerm.toLowerCase();

  const filtered = state.products.filter((product) => {
    const matchesCategory = state.activeCategory === 'All' || product.category === state.activeCategory;
    const searchable = `${product.name} ${product.category} ${product.barcode || ''} ${product.description || ''}`.toLowerCase();
    const matchesSearch = searchable.includes(searchLower);
    return matchesCategory && matchesSearch;
  });

  state.filteredProducts = filtered;
  elements.resultsCount.textContent = `${filtered.length} product${filtered.length === 1 ? '' : 's'} available`;

  if (!filtered.length) {
    elements.products.innerHTML = state.searchTerm
      ? '<div class="empty-state">No products found for your search. Try another keyword.</div>'
      : '<div class="empty-state">No products available in this category right now.</div>';
    return;
  }

  elements.products.innerHTML = filtered.map((product) => createProductCard(product)).join('');
  wireProductGridInteractions();
}

function createProductCard(product) {
  const primaryImage = product.images[0] || 'images/placeholder.svg';
  const stockMeta = getStockMeta(product.stock);
  const hasMrp = product.mrp && product.mrp > product.price;
  const highlightedName = highlightMatch(product.name, state.searchTerm);
  const highlightedCategory = highlightMatch(product.category, state.searchTerm);

  return `
    <article class="product-card" data-product-id="${escapeHtml(product.id)}">
      <button class="product-image-trigger" type="button" data-product-id="${escapeHtml(product.id)}" data-image-index="0" aria-label="Open full image">
        <div class="image-shell is-loading">
          <img class="product-image lazy-image" src="${escapeHtml(primaryImage)}" alt="${escapeHtml(product.name)}" loading="lazy">
        </div>
        <span class="stock-chip stock-${stockMeta.type}">${escapeHtml(stockMeta.label)}</span>
      </button>

      <div class="product-info">
        <h3 class="product-name">${highlightedName}</h3>
        <span class="product-category">${highlightedCategory}</span>

        <div class="price-row">
          <span class="price">${formatCurrency(product.price)}</span>
          ${hasMrp ? `<span class="mrp">MRP ${formatCurrency(product.mrp)}</span>` : ''}
        </div>

        <div class="qty-row">
          <label class="sr-only" for="qty-${escapeHtml(product.id)}">Quantity</label>
          <div class="qty-control">
            <button class="qty-btn" type="button" data-qty-action="minus">−</button>
            <input id="qty-${escapeHtml(product.id)}" class="qty-input" type="number" min="1" value="1">
            <button class="qty-btn" type="button" data-qty-action="plus">+</button>
          </div>
        </div>

        <button class="add-btn" data-product-id="${escapeHtml(product.id)}" type="button">Add to Cart</button>
      </div>

      ${product.images.length > 1 ? `
      <div class="card-thumbs">
        ${product.images
          .slice(0, 5)
          .map(
            (src, index) =>
              `<button class="thumb-btn ${index === 0 ? 'active' : ''}" type="button" data-thumb-index="${index}" aria-label="View image ${index + 1}"><img src="${escapeHtml(
                src
              )}" alt="${escapeHtml(product.name)} thumbnail ${index + 1}" loading="lazy"></button>`
          )
          .join('')}
      </div>
      ` : ''}
    </article>
  `;
}

function wireProductGridInteractions() {
  const cards = elements.products.querySelectorAll('.product-card');

  cards.forEach((card) => {
    card.addEventListener('click', (event) => {
      if (event.target.closest('.qty-control, .add-btn, .qty-btn, .thumb-btn, .product-image-trigger, .qty-input')) {
        return;
      }
      openProductModal(card.dataset.productId);
    });

    const quantityInput = card.querySelector('.qty-input');
    card.querySelectorAll('.qty-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const current = parseInt(quantityInput.value, 10) || 1;
        const next = button.dataset.qtyAction === 'plus' ? current + 1 : Math.max(1, current - 1);
        quantityInput.value = String(next);
      });
    });

    const addButton = card.querySelector('.add-btn');
    addButton.addEventListener('click', () => {
      const qty = parseInt(quantityInput.value, 10) || 1;
      addToCart(addButton.dataset.productId, qty);
    });

    const imageTrigger = card.querySelector('.product-image-trigger');
    imageTrigger.addEventListener('click', (event) => {
      event.stopPropagation();
      const product = state.products.find((item) => item.id === card.dataset.productId);
      if (product) {
        openImageViewer(product.images, Number(imageTrigger.dataset.imageIndex || 0));
      }
    });

    attachLongPress(imageTrigger, () => {
      const product = state.products.find((item) => item.id === card.dataset.productId);
      if (product) {
        openImageViewer(product.images, Number(imageTrigger.dataset.imageIndex || 0));
      }
    });

    card.querySelectorAll('.thumb-btn').forEach((thumbButton) => {
      thumbButton.addEventListener('click', (event) => {
        event.stopPropagation();
        const index = Number(thumbButton.dataset.thumbIndex || 0);
        const product = state.products.find((item) => item.id === card.dataset.productId);
        if (!product) return;
        updateCardPrimaryImage(card, product, index);
      });
    });
  });

  bindImageLoadEffects(elements.products);
}

function attachLongPress(node, callback) {
  let timer = null;
  let moved = false;

  node.addEventListener('touchstart', () => {
    moved = false;
    timer = window.setTimeout(() => {
      callback();
      timer = null;
    }, 420);
  }, { passive: true });

  node.addEventListener('touchmove', () => {
    moved = true;
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
  }, { passive: true });

  node.addEventListener('touchend', () => {
    if (moved && timer) {
      window.clearTimeout(timer);
      timer = null;
    }
  }, { passive: true });

  node.addEventListener('touchcancel', () => {
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
  }, { passive: true });
}

function updateCardPrimaryImage(card, product, index) {
  const img = card.querySelector('.product-image');
  const imageTrigger = card.querySelector('.product-image-trigger');
  if (!img || !imageTrigger) return;

  const safeIndex = clamp(index, 0, product.images.length - 1);
  img.parentElement.classList.add('is-loading');
  img.src = product.images[safeIndex] || 'images/placeholder.svg';
  imageTrigger.dataset.imageIndex = String(safeIndex);

  card.querySelectorAll('.thumb-btn').forEach((thumbNode, thumbIndex) => {
    thumbNode.classList.toggle('active', thumbIndex === safeIndex);
  });
}

function openProductModal(productId) {
  const product = state.products.find((item) => item.id === productId);
  if (!product) return;

  state.modalProductId = productId;
  state.modalImageIndex = 0;
  elements.productModalQty.value = '1';

  elements.productModalName.textContent = product.name;
  elements.productModalCategory.textContent = `Category: ${product.category}`;
  elements.productModalDescription.textContent = product.description || 'No description available.';
  elements.productModalPrice.textContent = formatCurrency(product.price);

  if (product.mrp && product.mrp > product.price) {
    elements.productModalMrp.textContent = `MRP ${formatCurrency(product.mrp)}`;
    elements.productModalMrp.classList.remove('is-hidden');
  } else {
    elements.productModalMrp.classList.add('is-hidden');
  }

  const stockMeta = getStockMeta(product.stock);
  elements.productModalStock.className = `modal-stock stock-${stockMeta.type}`;
  elements.productModalStock.textContent = stockMeta.label;

  renderProductModalGallery(product);

  elements.productModal.classList.remove('is-hidden');
  elements.productModal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
}

function renderProductModalGallery(product) {
  const currentImage = product.images[state.modalImageIndex] || product.images[0] || 'images/placeholder.svg';

  elements.productModalImageShell.innerHTML = `
    <button class="modal-image-trigger" type="button" aria-label="Open image viewer">
      <div class="image-shell is-loading">
        <img class="product-image lazy-image" src="${escapeHtml(currentImage)}" alt="${escapeHtml(product.name)}" loading="lazy">
      </div>
    </button>
  `;

  elements.productModalThumbs.innerHTML = product.images
    .map(
      (src, index) =>
        `<button class="thumb-btn ${index === state.modalImageIndex ? 'active' : ''}" type="button" data-modal-thumb-index="${index}" aria-label="Image ${index + 1}"><img src="${escapeHtml(
          src
        )}" alt="${escapeHtml(product.name)} thumbnail ${index + 1}" loading="lazy"></button>`
    )
    .join('');

  const trigger = elements.productModalImageShell.querySelector('.modal-image-trigger');
  trigger.addEventListener('click', () => openImageViewer(product.images, state.modalImageIndex));
  attachLongPress(trigger, () => openImageViewer(product.images, state.modalImageIndex));

  let startX = 0;
  trigger.addEventListener('touchstart', (event) => {
    startX = event.changedTouches[0].clientX;
  }, { passive: true });
  trigger.addEventListener('touchend', (event) => {
    const endX = event.changedTouches[0].clientX;
    const delta = endX - startX;
    if (Math.abs(delta) > 50) {
      shiftProductModalImage(delta < 0 ? 1 : -1);
    }
  }, { passive: true });

  elements.productModalThumbs.querySelectorAll('[data-modal-thumb-index]').forEach((button) => {
    button.addEventListener('click', () => {
      state.modalImageIndex = Number(button.dataset.modalThumbIndex || 0);
      renderProductModalGallery(product);
    });
  });

  bindImageLoadEffects(elements.productModalImageShell);
}

function closeProductModal() {
  elements.productModal.classList.add('is-hidden');
  elements.productModal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');
  state.modalProductId = null;
}

function shiftProductModalImage(direction) {
  if (!state.modalProductId) return;
  const product = state.products.find((item) => item.id === state.modalProductId);
  if (!product || product.images.length <= 1) return;

  state.modalImageIndex = (state.modalImageIndex + direction + product.images.length) % product.images.length;
  renderProductModalGallery(product);
}

function adjustModalQuantity(delta) {
  const current = parseInt(elements.productModalQty.value, 10) || 1;
  elements.productModalQty.value = String(Math.max(1, current + delta));
}

function addFromProductModal() {
  if (!state.modalProductId) return;
  const quantity = Math.max(1, parseInt(elements.productModalQty.value, 10) || 1);
  addToCart(state.modalProductId, quantity);
  closeProductModal();
}

function openImageViewer(images, startIndex = 0) {
  if (!images || !images.length) return;

  state.viewer.open = true;
  state.viewer.images = images;
  state.viewer.index = clamp(startIndex, 0, images.length - 1);
  resetViewerTransform();

  renderImageViewer();
  elements.imageViewer.classList.remove('is-hidden');
  elements.imageViewer.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
}

function closeImageViewer() {
  state.viewer.open = false;
  elements.imageViewer.classList.add('is-hidden');
  elements.imageViewer.setAttribute('aria-hidden', 'true');
  elements.imageViewerBackdrop.style.opacity = '';
  elements.imageViewerShell.style.transform = '';
  if (elements.productModal.classList.contains('is-hidden')) {
    document.body.classList.remove('modal-open');
  }
}

function renderImageViewer() {
  const current = state.viewer.images[state.viewer.index] || 'images/placeholder.svg';
  elements.imageViewerImg.src = current;
  elements.imageViewerImg.alt = `Product image ${state.viewer.index + 1}`;

  elements.imageViewerThumbs.innerHTML = state.viewer.images
    .map(
      (src, index) =>
        `<button class="thumb-btn ${index === state.viewer.index ? 'active' : ''}" type="button" data-viewer-index="${index}" aria-label="Image ${index + 1}"><img src="${escapeHtml(
          src
        )}" alt="Thumbnail ${index + 1}" loading="lazy"></button>`
    )
    .join('');

  elements.imageViewerThumbs.querySelectorAll('[data-viewer-index]').forEach((button) => {
    button.addEventListener('click', () => {
      state.viewer.index = Number(button.dataset.viewerIndex || 0);
      resetViewerTransform();
      renderImageViewer();
    });
  });

  bindImageLoadEffects(elements.imageViewerShell);
  applyViewerTransform();
}

function shiftViewerImage(direction) {
  if (!state.viewer.images.length) return;
  state.viewer.index = (state.viewer.index + direction + state.viewer.images.length) % state.viewer.images.length;
  resetViewerTransform();
  renderImageViewer();
}

function resetViewerTransform() {
  state.viewer.scale = 1;
  state.viewer.x = 0;
  state.viewer.y = 0;
  state.viewer.swipeDown = 0;
  applyViewerTransform();
}

function applyViewerTransform() {
  elements.imageViewerImg.style.transform = `translate(${state.viewer.x}px, ${state.viewer.y}px) scale(${state.viewer.scale})`;
}

function handleViewerWheel(event) {
  event.preventDefault();
  const delta = event.deltaY > 0 ? -0.2 : 0.2;
  const nextScale = clamp(state.viewer.scale + delta, 1, 4);
  state.viewer.scale = nextScale;
  if (nextScale === 1) {
    state.viewer.x = 0;
    state.viewer.y = 0;
  }
  applyViewerTransform();
}

function handleViewerMouseDown(event) {
  if (state.viewer.scale <= 1) return;
  state.viewer.dragging = true;
  state.viewer.dragStartX = event.clientX - state.viewer.x;
  state.viewer.dragStartY = event.clientY - state.viewer.y;
}

function handleViewerMouseMove(event) {
  if (!state.viewer.dragging) return;
  state.viewer.x = event.clientX - state.viewer.dragStartX;
  state.viewer.y = event.clientY - state.viewer.dragStartY;
  applyViewerTransform();
}

function handleViewerMouseUp() {
  state.viewer.dragging = false;
}

function handleViewerTouchStart(event) {
  if (!state.viewer.open) return;

  if (event.touches.length === 2) {
    state.viewer.pinchDistance = getTouchDistance(event.touches[0], event.touches[1]);
    state.viewer.baseScale = state.viewer.scale;
    return;
  }

  const touch = event.touches[0];
  state.viewer.touchStartX = touch.clientX;
  state.viewer.touchStartY = touch.clientY;
  state.viewer.startX = state.viewer.x;
  state.viewer.startY = state.viewer.y;
  state.viewer.swipeDown = 0;
}

function handleViewerTouchMove(event) {
  if (!state.viewer.open) return;

  if (event.touches.length === 2) {
    event.preventDefault();
    const distance = getTouchDistance(event.touches[0], event.touches[1]);
    const zoom = distance / (state.viewer.pinchDistance || distance);
    state.viewer.scale = clamp(state.viewer.baseScale * zoom, 1, 4);
    if (state.viewer.scale === 1) {
      state.viewer.x = 0;
      state.viewer.y = 0;
    }
    applyViewerTransform();
    return;
  }

  const touch = event.touches[0];
  const deltaX = touch.clientX - state.viewer.touchStartX;
  const deltaY = touch.clientY - state.viewer.touchStartY;

  if (state.viewer.scale > 1) {
    event.preventDefault();
    state.viewer.x = state.viewer.startX + deltaX;
    state.viewer.y = state.viewer.startY + deltaY;
    applyViewerTransform();
    return;
  }

  if (Math.abs(deltaY) > Math.abs(deltaX)) {
    state.viewer.swipeDown = deltaY;
    elements.imageViewerShell.style.transform = `translateY(${Math.max(0, deltaY)}px)`;
    const opacity = clamp(1 - Math.max(0, deltaY) / 300, 0.2, 1);
    elements.imageViewerBackdrop.style.opacity = String(opacity);
  }
}

function handleViewerTouchEnd(event) {
  if (!state.viewer.open) return;

  const changed = event.changedTouches[0];
  const deltaX = changed.clientX - state.viewer.touchStartX;
  const deltaY = changed.clientY - state.viewer.touchStartY;

  if (state.viewer.scale === 1 && Math.abs(deltaX) > 60 && Math.abs(deltaX) > Math.abs(deltaY)) {
    shiftViewerImage(deltaX < 0 ? 1 : -1);
  } else if (state.viewer.scale === 1 && state.viewer.swipeDown > 130) {
    closeImageViewer();
  }

  state.viewer.swipeDown = 0;
  elements.imageViewerShell.style.transform = '';
  elements.imageViewerBackdrop.style.opacity = '';
}

function getTouchDistance(a, b) {
  const dx = a.clientX - b.clientX;
  const dy = a.clientY - b.clientY;
  return Math.sqrt(dx * dx + dy * dy);
}

function getStockMeta(stock) {
  if (stock === null || Number.isNaN(stock)) {
    return { label: 'Stock available', type: 'ok' };
  }
  if (stock <= 0) {
    return { label: 'Out of stock', type: 'out' };
  }
  if (stock <= 10) {
    return { label: `Low stock: ${stock}`, type: 'low' };
  }
  return { label: `In stock: ${stock}`, type: 'ok' };
}

function getCategoryIcon(category) {
  const value = (category || '').toLowerCase();
  if (value.includes('clean')) return '🧽';
  if (value.includes('bucket')) return '🪣';
  if (value.includes('bottle')) return '🧴';
  if (value.includes('jerry')) return '🛢️';
  if (value.includes('house')) return '🏠';
  return '📦';
}

function addToCart(productId, quantity) {
  const product = state.products.find((item) => item.id === productId);
  if (!product) return;

  const existingItem = state.cart.find((item) => item.id === productId);
  if (existingItem) {
    existingItem.quantity += quantity;
  } else {
    state.cart.push({
      id: product.id,
      name: product.name,
      price: product.price,
      quantity,
      category: product.category
    });
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.cart));
  renderCart();
  showToast(`${product.name} added to cart`, 'success');
}

function renderCart() {
  const totalItems = state.cart.reduce((sum, item) => sum + item.quantity, 0);
  const totalAmount = state.cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

  elements.cartCount.textContent = String(totalItems);
  elements.cartTotalItems.textContent = `${totalItems} item${totalItems === 1 ? '' : 's'}`;
  elements.stickyItems.textContent = `${totalItems} item${totalItems === 1 ? '' : 's'}`;
  elements.stickyTotal.textContent = formatCurrency(totalAmount);
  elements.stickyCheckout.disabled = totalItems === 0;

  if (!state.cart.length) {
    elements.cartItems.innerHTML = '<div class="empty-state">Your cart is empty. Add products to continue.</div>';
    return;
  }

  elements.cartItems.innerHTML = state.cart
    .map(
      (item) => `
      <div class="cart-item">
        <div class="cart-item-info">
          <div class="cart-item-name">${escapeHtml(item.name)}</div>
          <div class="cart-item-meta">${formatCurrency(item.price)} × ${item.quantity}</div>
        </div>
        <div class="cart-actions">
          <button class="icon-btn" data-action="decrease" data-id="${escapeHtml(item.id)}" type="button">−</button>
          <span class="qty-pill">${item.quantity}</span>
          <button class="icon-btn" data-action="increase" data-id="${escapeHtml(item.id)}" type="button">+</button>
          <button class="remove-btn" data-action="remove" data-id="${escapeHtml(item.id)}" type="button">Remove</button>
        </div>
      </div>
    `
    )
    .join('');

  elements.cartItems.insertAdjacentHTML(
    'beforeend',
    `
      <div class="cart-item total-card">
        <div class="cart-item-info">
          <div class="cart-item-name">Estimated Total</div>
          <div class="cart-item-meta">${totalItems} items</div>
        </div>
        <div class="cart-item-name">${formatCurrency(totalAmount)}</div>
      </div>
    `
  );

  elements.cartItems.querySelectorAll('[data-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const action = button.dataset.action;
      const id = button.dataset.id;
      updateCartItem(id, action);
    });
  });
}

function updateCartItem(productId, action) {
  const cartItem = state.cart.find((item) => item.id === productId);
  if (!cartItem) return;

  if (action === 'increase') {
    cartItem.quantity += 1;
  } else if (action === 'decrease') {
    cartItem.quantity -= 1;
  } else if (action === 'remove') {
    state.cart = state.cart.filter((item) => item.id !== productId);
  }

  if (cartItem && cartItem.quantity <= 0) {
    state.cart = state.cart.filter((item) => item.id !== productId);
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.cart));
  renderCart();
}

function toggleCart(open) {
  elements.cartDrawer.classList.toggle('open', open);
  if (open) {
    elements.menuDrawer.classList.remove('open');
    elements.menuToggle.setAttribute('aria-expanded', 'false');
  }
  elements.drawerOverlay.classList.toggle('open', open || elements.menuDrawer.classList.contains('open'));
  elements.cartToggle.setAttribute('aria-expanded', String(open));
}

function toggleMenu(open) {
  elements.menuDrawer.classList.toggle('open', open);
  if (open) {
    elements.cartDrawer.classList.remove('open');
    elements.cartToggle.setAttribute('aria-expanded', 'false');
  }
  elements.drawerOverlay.classList.toggle('open', open || elements.cartDrawer.classList.contains('open'));
  elements.menuToggle.setAttribute('aria-expanded', String(open));
}

function closeAllDrawers() {
  elements.cartDrawer.classList.remove('open');
  elements.menuDrawer.classList.remove('open');
  elements.drawerOverlay.classList.remove('open');
  elements.cartToggle.setAttribute('aria-expanded', 'false');
  elements.menuToggle.setAttribute('aria-expanded', 'false');
}

function generateOrderId() {
  const today = new Date();
  const datePart = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;
  const uniqueSuffix = `${Date.now().toString().slice(-6)}${Math.floor(Math.random() * 900 + 100)}`;
  return `PS-${datePart}-${uniqueSuffix}`;
}

async function handleCheckout(event) {
  event.preventDefault();

  if (!state.cart.length) {
    showToast('Add items to your cart before placing the order.', 'info');
    return;
  }

  const formData = new FormData(elements.checkoutForm);
  const savedUser = JSON.parse(localStorage.getItem(USER_KEY) || '{}');
  const retailerName = savedUser?.shopName || state.user?.shopName || '';
  const retailerMobile = savedUser?.mobile || state.user?.mobile || '';
  const remarks = formData.get('remarks')?.toString().trim() || '';
  const orderId = generateOrderId();
  const dateTime = new Date().toISOString();

  const orderRows = state.cart.map((item) => ({
    'Order ID': orderId,
    Date: dateTime,
    'Shop Name': retailerName,
    Mobile: retailerMobile,
    Remarks: remarks,
    Product: item.name,
    Qty: item.quantity
  }));

  const sheetRows = orderRows.map((row) => [
    row['Order ID'],
    row.Date,
    row['Shop Name'],
    row.Mobile,
    row.Remarks,
    row.Product,
    row.Qty
  ]);

  const orderPayload = {
    orderId,
    dateTime,
    shopName: retailerName,
    mobile: retailerMobile,
    remarks,
    rows: orderRows,
    sheetRows,
    items: state.cart.map((item) => ({ ...item, orderId }))
  };

  const endpoint = elements.sheetEndpoint.value.trim();
  const localOrderRecord = {
    ...orderPayload,
    status: 'Pending Sync',
    createdAt: dateTime,
    syncedAt: null
  };

  await addOrderToQueue(localOrderRecord);

  if (endpoint && navigator.onLine) {
    try {
      const form = new FormData();
      form.append('data', JSON.stringify(orderPayload));
      await fetch(endpoint, {
        method: 'POST',
        body: form
      });
      await updateOrderStatus(orderId, 'Synced');
      await markOrderSynced(orderId);
      showToast('Order synced successfully', 'success');
    } catch (error) {
      console.error(error);
      await updateOrderStatus(orderId, 'Pending Sync');
      showToast('Order saved locally. Unable to sync now.', 'warning');
    }
  } else {
    showToast('Order saved offline and will sync when connection returns.', 'info');
  }

  const savedOrders = JSON.parse(localStorage.getItem(ORDERS_KEY) || '[]');
  savedOrders.push(orderPayload);
  localStorage.setItem(ORDERS_KEY, JSON.stringify(savedOrders));

  state.cart = [];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.cart));
  renderCart();
  elements.checkoutForm.reset();
  updateSyncStatus();
  closeAllDrawers();
}

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(PRODUCTS_STORE)) {
        db.createObjectStore(PRODUCTS_STORE, { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains(ORDERS_STORE)) {
        const orderStore = db.createObjectStore(ORDERS_STORE, { keyPath: 'orderId' });
        orderStore.createIndex('status', 'status', { unique: false });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function saveProductsToDb(products) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(PRODUCTS_STORE, 'readwrite');
    const store = tx.objectStore(PRODUCTS_STORE);
    products.forEach((product) => store.put(product));
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getProductsFromDb() {
  const db = await openDatabase();
  return new Promise((resolve) => {
    const tx = db.transaction(PRODUCTS_STORE, 'readonly');
    const store = tx.objectStore(PRODUCTS_STORE);
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => resolve([]);
  });
}

async function addOrderToQueue(orderRecord) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(ORDERS_STORE, 'readwrite');
    const store = tx.objectStore(ORDERS_STORE);
    store.put(orderRecord);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function updateOrderStatus(orderId, status) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(ORDERS_STORE, 'readwrite');
    const store = tx.objectStore(ORDERS_STORE);
    const request = store.get(orderId);
    request.onsuccess = () => {
      const order = request.result;
      if (order) {
        order.status = status;
        order.syncedAt = status === 'Synced' ? new Date().toISOString() : null;
        store.put(order);
      }
      tx.oncomplete = () => resolve();
    };
    tx.onerror = () => reject(tx.error);
  });
}

async function markOrderSynced(orderId) {
  const syncedCount = Number(localStorage.getItem(SYNCED_ORDERS_KEY) || '0');
  const syncedIds = JSON.parse(localStorage.getItem('patel-stores-synced-order-ids') || '[]');
  if (!syncedIds.includes(orderId)) {
    syncedIds.push(orderId);
    localStorage.setItem('patel-stores-synced-order-ids', JSON.stringify(syncedIds));
    localStorage.setItem(SYNCED_ORDERS_KEY, String(syncedCount + 1));
  }
  await removeOrderFromQueue(orderId);
}

async function removeOrderFromQueue(orderId) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(ORDERS_STORE, 'readwrite');
    const store = tx.objectStore(ORDERS_STORE);
    store.delete(orderId);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getPendingOrders() {
  const db = await openDatabase();
  return new Promise((resolve) => {
    const tx = db.transaction(ORDERS_STORE, 'readonly');
    const store = tx.objectStore(ORDERS_STORE);
    const request = store.getAll();
    request.onsuccess = () => {
      const orders = (request.result || []).filter((order) => order?.status === 'Pending Sync');
      state.pendingOrderCount = orders.length;
      updateSyncStatus();
      resolve(orders);
    };
    request.onerror = () => resolve([]);
  });
}

async function syncPendingOrders() {
  const endpoint = elements.sheetEndpoint.value.trim();
  if (!endpoint || !navigator.onLine) {
    await getPendingOrders();
    return;
  }

  const pendingOrders = await getPendingOrders();
  if (!pendingOrders.length) {
    updateSyncStatus();
    return;
  }

  for (const order of pendingOrders) {
    try {
      const form = new FormData();
      form.append('data', JSON.stringify(order));
      await fetch(endpoint, {
        method: 'POST',
        body: form
      });
      await updateOrderStatus(order.orderId, 'Synced');
      await markOrderSynced(order.orderId);
    } catch (error) {
      console.error(error);
    }
  }

  updateSyncStatus();
  showToast('Pending orders synced successfully', 'success');
}

function bindImageLoadEffects(scopeNode) {
  scopeNode.querySelectorAll('img.lazy-image').forEach((img) => {
    img.addEventListener('load', () => {
      const shell = img.closest('.image-shell');
      if (shell) {
        shell.classList.remove('is-loading');
      }
    }, { once: true });

    img.addEventListener('error', () => {
      img.src = 'images/placeholder.svg';
      const shell = img.closest('.image-shell');
      if (shell) {
        shell.classList.remove('is-loading');
      }
    }, { once: true });
  });
}

function showToast(message, type = 'success') {
  elements.toast.textContent = message;
  elements.toast.className = `toast toast-${type}`;
  requestAnimationFrame(() => {
    elements.toast.classList.add('show');
  });

  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    elements.toast.classList.remove('show');
  }, 2400);
}

function highlightMatch(value, term) {
  if (!term) {
    return escapeHtml(value);
  }

  const escaped = escapeHtml(value);
  const safeTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (!safeTerm) {
    return escaped;
  }

  const regex = new RegExp(`(${safeTerm})`, 'ig');
  return escaped.replace(regex, '<mark>$1</mark>');
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatCurrency(amount) {
  return `₹${Number(amount || 0).toFixed(2)}`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function cssEscape(value) {
  if (window.CSS && typeof window.CSS.escape === 'function') {
    return window.CSS.escape(value);
  }
  return String(value).replace(/"/g, '\\"');
}

document.addEventListener('DOMContentLoaded', init);
