import os

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Fast Food App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: var(--tg-theme-bg-color, #ffffff);
            --text-color: var(--tg-theme-text-color, #222222);
            --hint-color: var(--tg-theme-hint-color, #999999);
            --link-color: var(--tg-theme-link-color, #2481cc);
            --button-color: var(--tg-theme-button-color, #5288c1);
            --button-text-color: var(--tg-theme-button-text-color, #ffffff);
            --secondary-bg-color: var(--tg-theme-secondary-bg-color, #f0f0f0);
            --header-bg-color: var(--tg-theme-header-bg-color, #ffffff);
            --accent-color: #ff9800; /* Fast food orange accent */
            --danger-color: #f44336;
            --success-color: #4caf50;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            padding-bottom: 70px; /* Space for bottom nav */
            box-sizing: border-box;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }
        
        * { box-sizing: border-box; }

        /* Bottom Navigation */
        .bottom-nav {
            position: fixed;
            bottom: 0; left: 0; right: 0;
            height: 60px;
            background-color: var(--header-bg-color);
            display: flex;
            justify-content: space-around;
            align-items: center;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
            z-index: 1000;
        }
        
        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: var(--hint-color);
            text-decoration: none;
            font-size: 12px;
            width: 25%;
            height: 100%;
            cursor: pointer;
            transition: color 0.2s;
        }
        
        .nav-item.active {
            color: var(--accent-color);
        }
        
        .nav-icon { font-size: 20px; margin-bottom: 2px; }

        /* Pages */
        .page { display: none; padding: 16px; animation: fadeIn 0.3s ease; }
        .page.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

        /* Header */
        .page-header {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 16px;
            color: var(--text-color);
        }

        /* Products Grid */
        .products-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        
        .product-card {
            background: var(--secondary-bg-color);
            border-radius: 16px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        
        .product-img {
            width: 100%; height: 120px; object-fit: cover;
            background-color: #ddd;
        }
        
        .product-info { padding: 10px; flex: 1; display: flex; flex-direction: column; }
        .product-name { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
        .product-desc { font-size: 12px; color: var(--hint-color); margin-bottom: 8px; flex: 1; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;}
        .product-price { font-weight: 700; font-size: 14px; color: var(--accent-color); }
        
        .add-btn {
            background: var(--button-color);
            color: var(--button-text-color);
            border: none; border-radius: 8px;
            padding: 8px; font-weight: 600; font-size: 14px;
            cursor: pointer; margin-top: 8px;
        }
        
        .fav-btn {
            position: absolute; top: 8px; right: 8px;
            background: rgba(255,255,255,0.8); border-radius: 50%;
            width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
            font-size: 16px; border: none; cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        /* Categories Strip */
        .categories-strip {
            display: flex; overflow-x: auto; gap: 8px; padding-bottom: 12px;
            margin-bottom: 16px; scrollbar-width: none;
        }
        .categories-strip::-webkit-scrollbar { display: none; }
        .category-chip {
            background: var(--secondary-bg-color); color: var(--text-color);
            padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: 500;
            white-space: nowrap; cursor: pointer; border: 1px solid transparent;
        }
        .category-chip.active {
            background: var(--button-color); color: var(--button-text-color);
        }

        /* Search Input */
        .search-bar {
            width: 100%; padding: 12px 16px; border-radius: 12px;
            border: 1px solid var(--hint-color); background: var(--bg-color);
            color: var(--text-color); font-size: 16px; margin-bottom: 16px;
            font-family: 'Inter', sans-serif;
        }

        /* Profile & Orders */
        .profile-card {
            background: var(--secondary-bg-color); border-radius: 16px;
            padding: 16px; margin-bottom: 20px; text-align: center;
        }
        .profile-name { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
        .profile-phone { color: var(--hint-color); font-size: 14px; }
        
        .admin-btn {
            background: var(--danger-color); color: white; border: none;
            padding: 10px 20px; border-radius: 8px; font-weight: 600; margin-top: 12px;
            width: 100%; cursor: pointer;
        }

        .order-card {
            background: var(--secondary-bg-color); border-radius: 12px;
            padding: 16px; margin-bottom: 12px;
        }
        .order-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .order-id { font-weight: 700; }
        .order-status { font-size: 12px; padding: 4px 8px; border-radius: 4px; font-weight: 600; }
        .status-pending { background: #ffe0b2; color: #e65100; }
        .status-preparing { background: #bbdefb; color: #0d47a1; }
        .status-delivering { background: #e1bee7; color: #4a148c; }
        .status-completed { background: #c8e6c9; color: #1b5e20; }
        .status-cancelled { background: #ffcdd2; color: #b71c1c; }

        .order-total { font-weight: 700; margin-top: 8px; text-align: right; color: var(--accent-color); }

        /* Admin CSS */
        .admin-tabs { display: flex; gap: 8px; margin-bottom: 16px; }
        .admin-tab { flex: 1; text-align: center; padding: 10px; background: var(--secondary-bg-color); border-radius: 8px; cursor: pointer; font-weight: 600;}
        .admin-tab.active { background: var(--button-color); color: var(--button-text-color); }
        .admin-section { display: none; }
        .admin-section.active { display: block; }
        
        .stat-card { background: var(--secondary-bg-color); padding: 16px; border-radius: 12px; text-align: center; margin-bottom: 12px; }
        .stat-val { font-size: 24px; font-weight: 700; color: var(--accent-color); }
        .stat-label { font-size: 12px; color: var(--hint-color); }
        
        .action-btn { padding: 6px 12px; border-radius: 6px; border: none; font-weight: 600; cursor: pointer; font-size: 12px;}
        .btn-green { background: var(--success-color); color: white; }
        .btn-blue { background: var(--button-color); color: white; }
        .btn-red { background: var(--danger-color); color: white; }

        /* Loader */
        #loader { text-align: center; padding: 40px; color: var(--hint-color); }
    </style>
</head>
<body>

    <!-- Loading -->
    <div id="loader">Yuklanmoqda... 🍔</div>

    <!-- MAIN APP CONTAINER -->
    <div id="app" style="display:none;">

        <!-- PAGE: HOME (MENU) -->
        <div id="page-home" class="page active">
            <div class="page-header">Menyu</div>
            <div class="categories-strip" id="cat-strip"></div>
            <div class="products-grid" id="home-products"></div>
        </div>

        <!-- PAGE: SEARCH -->
        <div id="page-search" class="page">
            <div class="page-header">Qidiruv</div>
            <input type="text" id="search-input" class="search-bar" placeholder="Taom nomini yozing...">
            <div class="products-grid" id="search-results"></div>
        </div>

        <!-- PAGE: FAVORITES -->
        <div id="page-favs" class="page">
            <div class="page-header">Sevimlilar</div>
            <div id="fav-empty" style="text-align:center; color:var(--hint-color); padding: 40px; display:none;">
                Hali sevimli taomlar yo'q ❤️
            </div>
            <div class="products-grid" id="fav-products"></div>
        </div>

        <!-- PAGE: PROFILE & ORDERS -->
        <div id="page-profile" class="page">
            <div class="page-header">Profil</div>
            <div class="profile-card">
                <div class="profile-name" id="prof-name">Ism</div>
                <div class="profile-phone" id="prof-phone">+998...</div>
                <button id="btn-admin-access" class="admin-btn" style="display:none;" onclick="navTo('admin')">👑 Admin Panel</button>
            </div>
            
            <h3>Mening buyurtmalarim</h3>
            <div id="user-orders-list"></div>
        </div>

        <!-- PAGE: ADMIN PANEL -->
        <div id="page-admin" class="page">
            <div class="page-header">👑 Admin Panel</div>
            <div class="admin-tabs">
                <div class="admin-tab active" onclick="switchAdminTab('dash')">Statistika</div>
                <div class="admin-tab" onclick="switchAdminTab('orders')">Buyurtmalar</div>
                <div class="admin-tab" onclick="switchAdminTab('menu')">Tovarlar</div>
            </div>
            
            <!-- Dashboard -->
            <div id="admin-sec-dash" class="admin-section active">
                <div style="display:flex; gap:12px;">
                    <div class="stat-card" style="flex:1;">
                        <div class="stat-val" id="stat-revenue">0</div>
                        <div class="stat-label">Tushum (Bugun)</div>
                    </div>
                    <div class="stat-card" style="flex:1;">
                        <div class="stat-val" id="stat-orders">0</div>
                        <div class="stat-label">Buyurtmalar</div>
                    </div>
                </div>
            </div>
            
            <!-- Orders Manage -->
            <div id="admin-sec-orders" class="admin-section">
                <div id="admin-orders-list"></div>
            </div>
            
            <!-- CMS Manage -->
            <div id="admin-sec-menu" class="admin-section">
                <button class="action-btn btn-blue" style="width:100%; margin-bottom:12px; padding:12px;" onclick="showAddProductModal()">+ Yangi Tovar qo'shish</button>
                <div id="admin-cms-list"></div>
            </div>
        </div>

    </div>

    <!-- BOTTOM NAV -->
    <div class="bottom-nav" id="bottom-nav" style="display:none;">
        <div class="nav-item active" onclick="navTo('home')">
            <div class="nav-icon">🏠</div><div>Asosiy</div>
        </div>
        <div class="nav-item" onclick="navTo('search')">
            <div class="nav-icon">🔍</div><div>Qidiruv</div>
        </div>
        <div class="nav-item" onclick="navTo('favs')">
            <div class="nav-icon">❤️</div><div>Sevimlilar</div>
        </div>
        <div class="nav-item" onclick="navTo('profile')">
            <div class="nav-icon">👤</div><div>Profil</div>
        </div>
    </div>
    
    <!-- Modal for adding product (simplified using JS prompts for now to save space) -->

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        
        const userId = tg.initDataUnsafe?.user?.id || 0;
        let globalCategories = [];
        let globalFavorites = [];
        let isAdmin = false;
        let cart = {}; // product_id -> quantity
        
        const API_BASE = window.location.origin;

        // Initialize App
        async function initApp() {
            try {
                // 1. Fetch Profile to know if admin
                const resProf = await fetch(`${API_BASE}/api/user?user_id=${userId}`);
                if(resProf.ok) {
                    const data = await resProf.json();
                    if(data.user) {
                        document.getElementById('prof-name').innerText = data.user.name;
                        document.getElementById('prof-phone').innerText = data.user.phone || 'Telefon yo\\'q';
                        isAdmin = data.user.is_admin;
                        if(isAdmin) document.getElementById('btn-admin-access').style.display = 'block';
                        renderUserOrders(data.orders);
                    }
                }
                
                // 2. Fetch Favorites
                if(userId) {
                    const resFav = await fetch(`${API_BASE}/api/favorites?user_id=${userId}`);
                    if(resFav.ok) {
                        const favData = await resFav.json();
                        globalFavorites = favData.favorites.map(f => f.id);
                    }
                }
                
                // 3. Fetch Menu Categories
                const resMenu = await fetch(`${API_BASE}/api/menu`);
                if(resMenu.ok) {
                    const menuData = await resMenu.json();
                    globalCategories = menuData.categories || [];
                    renderMenu();
                }
                
                // Show App
                document.getElementById('loader').style.display = 'none';
                document.getElementById('app').style.display = 'block';
                document.getElementById('bottom-nav').style.display = 'flex';
                
            } catch (err) {
                document.getElementById('loader').innerText = "Xatolik yuz berdi! Qayta yuklang.";
                console.error(err);
            }
        }
        
        // Navigation
        function navTo(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(`page-${pageId}`).classList.add('active');
            
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            if(pageId !== 'admin') {
                const map = {'home':0, 'search':1, 'favs':2, 'profile':3};
                if(map[pageId] !== undefined) {
                    document.querySelectorAll('.nav-item')[map[pageId]].classList.add('active');
                }
            }
            
            if(pageId === 'favs') loadFavs();
            if(pageId === 'admin') loadAdmin();
            
            // Toggle Main Button (Cart)
            updateMainButton();
        }
        
        // RENDER MENU
        let currentCatId = null;
        function renderMenu() {
            const strip = document.getElementById('cat-strip');
            strip.innerHTML = '';
            
            if(!globalCategories.length) return;
            
            globalCategories.forEach((cat, idx) => {
                const chip = document.createElement('div');
                chip.className = `category-chip ${idx === 0 ? 'active' : ''}`;
                chip.innerText = `${cat.emoji} ${cat.name}`;
                chip.onclick = () => {
                    document.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
                    chip.classList.add('active');
                    currentCatId = cat.id;
                    renderProductsGrid('home-products', cat.products);
                };
                strip.appendChild(chip);
                if(idx === 0) currentCatId = cat.id;
            });
            
            renderProductsGrid('home-products', globalCategories[0].products);
        }
        
        function renderProductsGrid(containerId, products) {
            const container = document.getElementById(containerId);
            container.innerHTML = '';
            
            products.forEach(p => {
                const isFav = globalFavorites.includes(p.id);
                const card = document.createElement('div');
                card.className = 'product-card';
                card.innerHTML = `
                    <button class="fav-btn" onclick="toggleFav(${p.id}, this)">${isFav ? '❤️' : '🤍'}</button>
                    <img src="${p.image_url || 'https://via.placeholder.com/150'}" class="product-img">
                    <div class="product-info">
                        <div class="product-name">${p.name}</div>
                        <div class="product-desc">${p.description}</div>
                        <div class="product-price">${p.price.toLocaleString()} UZS</div>
                        <button class="add-btn" onclick="addToCart(${p.id}, '${p.name.replace(/'/g, "\\'")}', ${p.price})">Qo'shish</button>
                    </div>
                `;
                container.appendChild(card);
            });
        }
        
        // Favorites logic
        async function toggleFav(productId, btnNode) {
            const isAdding = btnNode.innerText === '🤍';
            btnNode.innerText = isAdding ? '❤️' : '🤍';
            if(isAdding) globalFavorites.push(productId);
            else globalFavorites = globalFavorites.filter(id => id !== productId);
            
            try {
                await fetch(`${API_BASE}/api/favorites/toggle`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: userId, product_id: productId})
                });
            } catch(e) {}
        }
        
        function loadFavs() {
            const favProducts = [];
            globalCategories.forEach(cat => {
                cat.products.forEach(p => {
                    if(globalFavorites.includes(p.id)) favProducts.push(p);
                });
            });
            
            if(favProducts.length === 0) {
                document.getElementById('fav-empty').style.display = 'block';
                document.getElementById('fav-products').innerHTML = '';
            } else {
                document.getElementById('fav-empty').style.display = 'none';
                renderProductsGrid('fav-products', favProducts);
            }
        }
        
        // Search Logic
        let searchTimeout = null;
        document.getElementById('search-input').addEventListener('input', (e) => {
            const q = e.target.value.trim();
            if(searchTimeout) clearTimeout(searchTimeout);
            searchTimeout = setTimeout(async () => {
                if(!q) { document.getElementById('search-results').innerHTML = ''; return; }
                const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(q)}`);
                if(res.ok) {
                    const data = await res.json();
                    renderProductsGrid('search-results', data.results || []);
                }
            }, 500);
        });
        
        // User Orders
        function renderUserOrders(orders) {
            const container = document.getElementById('user-orders-list');
            container.innerHTML = '';
            if(!orders || !orders.length) {
                container.innerHTML = '<p style="color:var(--hint-color); text-align:center;">Hali buyurtmalar yo\\'q</p>';
                return;
            }
            
            orders.forEach(o => {
                let statusClass = `status-${o.status}`;
                container.innerHTML += `
                    <div class="order-card">
                        <div class="order-header">
                            <span class="order-id">#${o.id}</span>
                            <span class="order-status ${statusClass}">${o.status.toUpperCase()}</span>
                        </div>
                        <div style="font-size:12px; color:var(--hint-color)">${new Date(o.created_at).toLocaleString()}</div>
                        <div class="order-total">${o.total_amount.toLocaleString()} UZS</div>
                    </div>
                `;
            });
        }
        
        // --- CART & TG BUTTON ---
        function addToCart(id, name, price) {
            if(!cart[id]) cart[id] = {name, price, qty:0};
            cart[id].qty++;
            tg.HapticFeedback.impactOccurred('light');
            updateMainButton();
        }
        
        function updateMainButton() {
            let total = 0;
            let count = 0;
            Object.values(cart).forEach(item => {
                total += item.price * item.qty;
                count += item.qty;
            });
            
            if(count > 0 && document.getElementById('page-admin').classList.contains('active') === false) {
                tg.MainButton.text = `Savatga o'tish (${total.toLocaleString()} UZS)`;
                tg.MainButton.show();
            } else {
                tg.MainButton.hide();
            }
        }
        
        tg.MainButton.onClick(() => {
            // We can send data back to bot to process the cart!
            const cartItems = [];
            Object.keys(cart).forEach(id => {
                if(cart[id].qty > 0) cartItems.push({id: parseInt(id), qty: cart[id].qty});
            });
            tg.sendData(JSON.stringify({action: "checkout", items: cartItems}));
        });
        
        // --- ADMIN PANEL ---
        function switchAdminTab(tab) {
            document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(`admin-sec-${tab}`).classList.add('active');
            
            if(tab === 'orders') fetchAdminOrders();
        }
        
        async function loadAdmin() {
            try {
                const res = await fetch(`${API_BASE}/api/admin/dashboard?user_id=${userId}`);
                if(res.ok) {
                    const data = await res.json();
                    document.getElementById('stat-revenue').innerText = (data.stats.total_sum || 0).toLocaleString();
                    document.getElementById('stat-orders').innerText = data.stats.total_orders || 0;
                }
                fetchAdminOrders();
                renderAdminMenu();
            } catch(e) { console.error(e); }
        }
        
        async function fetchAdminOrders() {
            try {
                const res = await fetch(`${API_BASE}/api/admin/orders?user_id=${userId}&status=active`);
                if(res.ok) {
                    const data = await res.json();
                    const container = document.getElementById('admin-orders-list');
                    container.innerHTML = '';
                    if(!data.orders.length) {
                        container.innerHTML = '<p>Faol buyurtmalar yo\\'q.</p>';
                        return;
                    }
                    data.orders.forEach(o => {
                        let statusHTML = '';
                        if(o.status === 'pending') {
                            statusHTML = `
                                <button class="action-btn btn-blue" onclick="changeStatus(${o.id}, 'preparing')">Tayyorlashni boshlash</button>
                                <button class="action-btn btn-red" onclick="changeStatus(${o.id}, 'cancelled')">Bekor qilish</button>
                            `;
                        } else if(o.status === 'preparing') {
                            statusHTML = `
                                <button class="action-btn btn-blue" onclick="changeStatus(${o.id}, 'delivering')">Yetkazishga berish</button>
                            `;
                        } else if(o.status === 'delivering') {
                            statusHTML = `
                                <button class="action-btn btn-green" onclick="changeStatus(${o.id}, 'completed')">Yakunlash</button>
                            `;
                        }
                        
                        let itemsHtml = o.items.map(i => `${i.product_name} x${i.quantity}`).join('<br>');
                        
                        container.innerHTML += `
                            <div class="order-card" style="border:1px solid var(--accent-color);">
                                <div class="order-header">
                                    <span class="order-id">#${o.id} - ${o.user_name}</span>
                                    <span class="order-status status-${o.status}">${o.status}</span>
                                </div>
                                <div style="font-size:12px; margin-bottom:8px;">📞 ${o.user_phone}<br>📍 ${o.address || 'Kiritilmagan'}</div>
                                <div style="font-size:12px; margin-bottom:8px;">${itemsHtml}</div>
                                <div class="order-total" style="margin-bottom:8px;">${o.total_amount.toLocaleString()} UZS</div>
                                <div style="display:flex; gap:8px; justify-content:flex-end;">
                                    ${statusHTML}
                                </div>
                            </div>
                        `;
                    });
                }
            } catch(e) {}
        }
        
        async function changeStatus(orderId, newStatus) {
            if(!confirm(`Buyurtma holatini '${newStatus}' ga o'zgartirasizmi?`)) return;
            try {
                const res = await fetch(`${API_BASE}/api/admin/order/status`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: userId, order_id: orderId, status: newStatus})
                });
                if(res.ok) fetchAdminOrders(); // reload
            } catch(e) {}
        }
        
        // ADMIN CMS
        function renderAdminMenu() {
            const container = document.getElementById('admin-cms-list');
            container.innerHTML = '';
            
            globalCategories.forEach(cat => {
                container.innerHTML += `<div style="background:var(--button-color); color:white; padding:8px; border-radius:8px; margin-top:16px; font-weight:bold;">Kategoriya: ${cat.emoji} ${cat.name}</div>`;
                
                cat.products.forEach(p => {
                    container.innerHTML += `
                        <div class="order-card" style="display:flex; gap:12px; align-items:center;">
                            <img src="${p.image_url}" style="width:60px; height:60px; border-radius:8px; object-fit:cover;">
                            <div style="flex:1;">
                                <div style="font-weight:bold;">${p.name}</div>
                                <div style="color:var(--accent-color);">${p.price} UZS</div>
                            </div>
                            <div>
                                <button class="action-btn btn-red" onclick="deleteProduct(${p.id})">🗑</button>
                            </div>
                        </div>
                    `;
                });
            });
        }
        
        async function showAddProductModal() {
            // Very simple prompt based add product
            const catId = prompt("Kategoriya ID sini kiriting (1 = Burger, 2 = Pitsa...):", "1");
            if(!catId) return;
            const name = prompt("Tovar nomi:", "Yangi Tovar");
            if(!name) return;
            const priceStr = prompt("Narxi (raqamda):", "25000");
            if(!priceStr) return;
            const img = prompt("Rasm URL (HTTP link):", "https://via.placeholder.com/150");
            
            try {
                const res = await fetch(`${API_BASE}/api/admin/products`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: userId,
                        action: 'add',
                        category_id: catId,
                        name: name,
                        price: parseInt(priceStr),
                        image_url: img
                    })
                });
                if(res.ok) {
                    alert("Muvaqqiyatli qo'shildi! Qayta yuklang.");
                }
            } catch(e) { alert("Xato"); }
        }
        
        async function deleteProduct(pId) {
            if(!confirm("O'chirasizmi?")) return;
            try {
                const res = await fetch(`${API_BASE}/api/admin/products`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: userId, action: 'delete', product_id: pId})
                });
                if(res.ok) {
                    alert("O'chirildi! Qayta yuklang.");
                }
            } catch(e) {}
        }
        
        // Start App
        initApp();
        
    </script>
</body>
</html>
"""

os.makedirs("fastfood_bot/webapp", exist_ok=True)
with open("fastfood_bot/webapp/app.html", "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)
    
print("app.html yaraldi!")
