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
    user: null
  };

  const elements = {
    welcomePill: document.getElementById("welcome-pill"),
    logoutBtn: document.getElementById("logout-btn"),
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
    cartCount: document.getElementById('cart-count'),
    cartTotalItems: document.getElementById('cart-total-items'),
    cartItems: document.getElementById('cart-items'),
    cartToggle: document.getElementById('cart-toggle'),
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
    toast: document.getElementById('toast')
  };

  function init() {
    bindEvents();
    registerServiceWorker();
    initSyncSystem();

    const savedUser = localStorage.getItem(USER_KEY);
    if (savedUser) {
      const user = JSON.parse(savedUser);
      state.user = user;
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
      state.searchTerm = event.target.value.trim();
      renderProducts();
    });

    document.querySelectorAll('.filter-chip').forEach((button) => {
      button.addEventListener('click', () => {
        document.querySelectorAll('.filter-chip').forEach((chip) => chip.classList.remove('active'));
        button.classList.add('active');
        state.activeCategory = button.dataset.category;
        renderProducts();
      });
    });

    elements.cartToggle.addEventListener('click', () => toggleCart(true));
    elements.closeCart.addEventListener('click', () => toggleCart(false));
    elements.menuToggle.addEventListener('click', () => toggleMenu(true));
    elements.closeMenu.addEventListener('click', () => toggleMenu(false));
    elements.drawerOverlay.addEventListener('click', () => closeAllDrawers());

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeAllDrawers();
      }
    });

    elements.checkoutForm.addEventListener('submit', handleCheckout);
    elements.syncStatus.addEventListener('click', toggleSyncPanel);
    elements.retrySync.addEventListener('click', () => syncPendingOrders());
  }

  function initSyncSystem() {
    updateSyncStatus();
    window.addEventListener('online', () => {
      updateSyncStatus();
      syncPendingOrders();
      showToast('Connection restored. Syncing pending orders.');
    });
    window.addEventListener('offline', () => {
      updateSyncStatus();
      showToast('Offline mode enabled. Orders will sync when connection returns.');
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
    if (!elements.syncStatus) return;
    const pendingCount = state.pendingOrderCount || 0;
    const online = navigator.onLine;
    const label = online ? '● Online' : '● Offline';
    elements.syncStatus.textContent = pendingCount > 0 ? `${label} (${pendingCount})` : label;
    elements.syncStatus.style.background = online ? 'rgba(255,255,255,.16)' : 'rgba(245,158,11,.25)';
    if (elements.syncSummary) {
      const syncedCount = Number(localStorage.getItem(SYNCED_ORDERS_KEY) || '0');
      elements.syncSummary.textContent = online
        ? `${pendingCount} pending • ${syncedCount} synced • ready to sync`
        : `${pendingCount} pending • ${syncedCount} synced • offline`;
    }
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

    if(state.user){
        elements.welcomePill.textContent = "Welcome, " + state.user.shopName;
        elements.welcomePill.classList.remove("is-hidden");
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

    elements.logoutBtn.classList.remove("is-hidden");

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
      showToast('Signed in offline using saved retailer details.');
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
        showToast('Signed in offline using saved retailer details.');
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
      const cachedProducts = await getProductsFromDb();
      if (cachedProducts.length) {
        state.products = cachedProducts;
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
      const products = data.products || [];
      state.products = products;
      await saveProductsToDb(products);
      renderProducts();
    } catch (error) {
      elements.products.innerHTML = '<div class="empty-state">Products could not be loaded. Please refresh the page.</div>';
      elements.resultsCount.textContent = 'Unavailable';
      showToast('Unable to load products from the catalog.');
      console.error(error);
    }
  }

  function renderProducts() {
    const filtered = state.products.filter((product) => {
      const matchesCategory = state.activeCategory === 'All' || product.category === state.activeCategory;
      const searchableText = `${product.name} ${product.category} ${product.barcode || ''} ${product.description || ''}`.toLowerCase();
      const matchesSearch = searchableText.includes(state.searchTerm.toLowerCase());
      return matchesCategory && matchesSearch;
    });

    state.filteredProducts = filtered;
    elements.resultsCount.textContent = `${filtered.length} product${filtered.length === 1 ? '' : 's'} available`;

    if (!filtered.length) {
      elements.products.innerHTML = '<div class="empty-state">No products match your search. Try another keyword.</div>';
      return;
    }

    elements.products.innerHTML = filtered.map((product) => createProductCard(product)).join('');

    document.querySelectorAll('.add-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const card = button.closest('.product-card');
        const quantityInput = card.querySelector('.qty-input');
        const qty = parseInt(quantityInput.value, 10) || 1;
        addToCart(button.dataset.productId, qty);
      });
    });

    document.querySelectorAll('.qty-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const card = button.closest('.product-card');
        const quantityInput = card.querySelector('.qty-input');
        const currentValue = parseInt(quantityInput.value, 10) || 1;
        const nextValue = button.dataset.qtyAction === 'plus' ? currentValue + 1 : Math.max(1, currentValue - 1);
        quantityInput.value = nextValue;
      });
    });

    document.querySelectorAll('.product-card img').forEach((img) => {
      img.addEventListener('error', () => {
        img.src = 'images/placeholder.svg';
      });
    });
  }

  function createProductCard(product) {
    const imagePath = product.image && product.image.trim() ? product.image : 'images/placeholder.svg';

    return `
      <article class="product-card">
        <div class="product-card-media">
          <img src="${imagePath}" alt="${product.name}" loading="lazy" onerror="this.onerror=null;this.src='images/placeholder.svg';">
        </div>
        <div class="product-info">
          <div class="product-name">${product.name}</div>
          <span class="product-category">${product.category}</span>
          <div class="price-row">
            <span class="price">₹${product.price}</span>
          </div>
          <div class="qty-row">
            <label class="sr-only" for="qty-${product.id}">Quantity</label>
            <div class="qty-control">
              <button class="qty-btn" type="button" data-qty-action="minus">−</button>
              <input id="qty-${product.id}" class="qty-input" type="number" min="1" value="1">
              <button class="qty-btn" type="button" data-qty-action="plus">+</button>
            </div>
          </div>
          <button class="add-btn" data-product-id="${product.id}" type="button">🛒 Add to Cart</button>
        </div>
      </article>
    `;
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
    showToast(`${product.name} added to cart`);
  }

  function renderCart() {
    const totalItems = state.cart.reduce((sum, item) => sum + item.quantity, 0);
    const totalAmount = state.cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

    elements.cartCount.textContent = totalItems;
    elements.cartTotalItems.textContent = `${totalItems} item${totalItems === 1 ? '' : 's'}`;

    if (!state.cart.length) {
      elements.cartItems.innerHTML = '<div class="empty-state">Your basket is empty. Add wholesale essentials to start ordering.</div>';
      return;
    }

    elements.cartItems.innerHTML = state.cart.map((item) => `
      <div class="cart-item">
        <div class="cart-item-info">
          <div class="cart-item-name">${item.name}</div>
          <div class="cart-item-meta">₹${item.price} × ${item.quantity}</div>
        </div>
        <div class="cart-actions">
          <button class="icon-btn" data-action="decrease" data-id="${item.id}" type="button">−</button>
          <span class="qty-pill">${item.quantity}</span>
          <button class="icon-btn" data-action="increase" data-id="${item.id}" type="button">+</button>
          <button class="remove-btn" data-action="remove" data-id="${item.id}" type="button">Remove</button>
        </div>
      </div>
    `).join('');

    elements.cartItems.insertAdjacentHTML('beforeend', `
      <div class="cart-item">
        <div class="cart-item-info">
          <div class="cart-item-name">Estimated Total</div>
          <div class="cart-item-meta">${totalItems} items</div>
        </div>
        <div class="cart-item-name">₹${totalAmount}</div>
      </div>
    `);

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
      elements.cartToggle.classList.add('hidden');
    } else {
      elements.cartToggle.classList.remove('hidden');
    }
    elements.drawerOverlay.classList.toggle('open', open || elements.menuDrawer.classList.contains('open'));
    elements.cartToggle.setAttribute('aria-expanded', String(open));
  }

  function toggleMenu(open) {
    elements.menuDrawer.classList.toggle('open', open);
    if (open) {
      elements.cartDrawer.classList.remove('open');
      elements.cartToggle.setAttribute('aria-expanded', 'false');
      elements.cartToggle.classList.remove('hidden');
    }
    elements.drawerOverlay.classList.toggle('open', open || elements.cartDrawer.classList.contains('open'));
    elements.menuToggle.setAttribute('aria-expanded', String(open));
  }

  function closeAllDrawers() {
    elements.cartDrawer.classList.remove('open');
    elements.menuDrawer.classList.remove('open');
    elements.drawerOverlay.classList.remove('open');
    elements.cartToggle.classList.remove('hidden');
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
      showToast('Add items to your basket before placing the order.');
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
      items: state.cart.map((item) => ({
        ...item,
        orderId
      }))
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
        showToast('Order Synced Successfully');
      } catch (error) {
        console.error(error);
        await updateOrderStatus(orderId, 'Pending Sync');
        showToast('The order was saved locally, but the sheet endpoint could not be reached.');
      }
    } else {
      showToast('Order saved offline and will sync when connection returns.');
    }

    const savedOrders = JSON.parse(localStorage.getItem(ORDERS_KEY) || '[]');
    savedOrders.push(orderPayload);
    localStorage.setItem(ORDERS_KEY, JSON.stringify(savedOrders));

    state.cart = [];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.cart));
    renderCart();
    elements.checkoutForm.reset();
    updateSyncStatus();
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
    if (pendingOrders.length) {
      showToast('Order Synced Successfully');
    }
  }

  function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add('show');
    window.clearTimeout(showToast.timeout);
    showToast.timeout = window.setTimeout(() => {
      elements.toast.classList.remove('show');
    }, 2200);
  }

  document.addEventListener('DOMContentLoaded', init);
