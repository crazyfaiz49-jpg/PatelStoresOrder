  const STORAGE_KEY = 'patel-stores-cart';
  const ORDERS_KEY = 'patel-stores-orders';

  const state = {
    products: [],
    filteredProducts: [],
    activeCategory: 'All',
    searchTerm: '',
    cart: JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  };

  const elements = {
    search: document.getElementById('search'),
    products: document.getElementById('products'),
    resultsCount: document.getElementById('results-count'),
    cartCount: document.getElementById('cart-count'),
    cartTotalItems: document.getElementById('cart-total-items'),
    cartItems: document.getElementById('cart-items'),
    cartToggle: document.getElementById('cart-toggle'),
    closeCart: document.getElementById('close-cart'),
    drawerOverlay: document.getElementById('drawer-overlay'),
    cartDrawer: document.getElementById('cart-drawer'),
    checkoutForm: document.getElementById('checkout-form'),
    sheetEndpoint: document.getElementById('sheet-endpoint'),
    toast: document.getElementById('toast')
  };

  function init() {
    bindEvents();
    loadProducts();
    renderCart();
  }

  function bindEvents() {
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
    elements.drawerOverlay.addEventListener('click', () => toggleCart(false));

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        toggleCart(false);
      }
    });

    elements.checkoutForm.addEventListener('submit', handleCheckout);
  }

  async function loadProducts() {
    try {
      const response = await fetch('products.json');
      if (!response.ok) {
        throw new Error('Unable to load products');
      }

      const data = await response.json();
      state.products = data.products || [];
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
        <img src="${imagePath}" alt="${product.name}" loading="lazy" onerror="this.onerror=null;this.src='images/placeholder.svg';">
        <div class="product-info">
          <div class="product-name">${product.name}</div>
          <span class="product-category">${product.category}</span>
          <p class="product-desc">${product.description || 'Wholesale ready product for retailers.'}</p>
          <div class="price-row">
            <span class="price">₹${product.price}</span>
            <span class="product-category">${product.barcode || 'SKU'}</span>
          </div>
          <div class="qty-row">
            <label class="sr-only" for="qty-${product.id}">Quantity</label>
            <input id="qty-${product.id}" class="qty-input" type="number" min="1" value="1">
          </div>
          <button class="add-btn" data-product-id="${product.id}" type="button">Add to Cart</button>
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
    elements.drawerOverlay.classList.toggle('open', open);
    elements.cartToggle.setAttribute('aria-expanded', String(open));
  }

  async function handleCheckout(event) {
    event.preventDefault();

    if (!state.cart.length) {
      showToast('Add items to your basket before placing the order.');
      return;
    }

    const formData = new FormData(elements.checkoutForm);
    const orderPayload = {
      customerName: formData.get('customerName')?.toString().trim() || '',
      mobileNumber: formData.get('customerMobile')?.toString().trim() || '',
      remarks: formData.get('remarks')?.toString().trim() || '',
      items: state.cart,
      submittedAt: new Date().toISOString()
    };

    const endpoint = elements.sheetEndpoint.value.trim();

    if (endpoint) {
      try {
        const form = new FormData();

        form.append("data", JSON.stringify(orderPayload));

        await fetch(endpoint, {
          method: "POST",
          body: form
        });
      } catch (error) {
        console.error(error);
        showToast('The order was saved locally, but the sheet endpoint could not be reached.');
      }
    } else {
      showToast('Set your Apps Script endpoint to send the order to Google Sheets.');
    }

    const savedOrders = JSON.parse(localStorage.getItem(ORDERS_KEY) || '[]');
    savedOrders.push(orderPayload);
    localStorage.setItem(ORDERS_KEY, JSON.stringify(savedOrders));

    state.cart = [];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.cart));
    renderCart();
    elements.checkoutForm.reset();
    showToast('Order submitted successfully.');
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
