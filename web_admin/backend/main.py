"""
Fast Food Bot — Web Admin Panel Backend
FastAPI + asyncpg / SQLite fallback
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List

import aiosqlite
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── Konfiguratsiya ──────────────────────────────────────────────────
DB_URI = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URI")
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "fastfood_bot", "database", "fastfood.db")

app = FastAPI(title="Fast Food Admin API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATUS_LABELS = {
    "pending":    "⏳ Kutilmoqda",
    "preparing":  "🍳 Tayyorlanmoqda",
    "delivering": "🚗 Yetkazilmoqda",
    "completed":  "✅ Tugallandi",
    "cancelled":  "❌ Bekor qilingan",
}

# ── DB yordamchi ─────────────────────────────────────────────────────

async def _get_pool():
    """asyncpg pool yoki SQLite connection qaytaradi."""
    if DB_URI:
        try:
            import asyncpg
            if not hasattr(app.state, 'pg_pool') or app.state.pg_pool is None:
                app.state.pg_pool = await asyncpg.create_pool(DB_URI)
            return app.state.pg_pool, "postgres"
        except Exception as e:
            logging.warning(f"PostgreSQL connection failed: {e}")
    return None, "sqlite"


async def _query(sql: str, *args):
    """Universal query: PostgreSQL yoki SQLite."""
    pool, db_type = await _get_pool()

    if db_type == "postgres":
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]
    else:
        import re
        sq = re.sub(r'\$\d+', '?', sql)
        async with aiosqlite.connect(SQLITE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sq, args)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def _fetchval(sql: str, *args):
    pool, db_type = await _get_pool()
    if db_type == "postgres":
        async with pool.acquire() as conn:
            return await conn.fetchval(sql, *args)
    else:
        import re
        sq = re.sub(r'\$\d+', '?', sql)
        async with aiosqlite.connect(SQLITE_PATH) as db:
            cur = await db.execute(sq, args)
            row = await cur.fetchone()
            return row[0] if row else None


async def _execute(sql: str, *args):
    pool, db_type = await _get_pool()
    if db_type == "postgres":
        async with pool.acquire() as conn:
            await conn.execute(sql, *args)
    else:
        import re
        sq = re.sub(r'\$\d+', '?', sql)
        async with aiosqlite.connect(SQLITE_PATH) as db:
            await db.execute(sq, args)
            await db.commit()


# ── Startup / Shutdown ────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logging.info("Web Admin API started.")

@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, 'pg_pool') and app.state.pg_pool:
        await app.state.pg_pool.close()


# ── Modellar ──────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: str

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ── API: Statistika ───────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    today = date.today().isoformat()
    users = await _fetchval("SELECT COUNT(*) FROM users") or 0
    orders_total = await _fetchval("SELECT COUNT(*) FROM orders") or 0
    orders_today = await _fetchval("SELECT COUNT(*) FROM orders WHERE created_at >= $1", today) or 0
    revenue_total = await _fetchval("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status = $1", "completed") or 0
    revenue_today = await _fetchval(
        "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status = $1 AND created_at >= $2",
        "completed", today
    ) or 0
    pending = await _fetchval("SELECT COUNT(*) FROM orders WHERE status = $1", "pending") or 0
    preparing = await _fetchval("SELECT COUNT(*) FROM orders WHERE status = $1", "preparing") or 0

    return {
        "users": users,
        "orders_total": orders_total,
        "orders_today": orders_today,
        "revenue_total": revenue_total,
        "revenue_today": revenue_today,
        "pending": pending,
        "preparing": preparing,
    }


# ── API: Buyurtmalar ──────────────────────────────────────────────────

@app.get("/api/orders")
async def get_orders(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
):
    if status and status != "all":
        rows = await _query("""
            SELECT o.id, o.user_id, o.total_amount, o.status, o.delivery_address,
                   o.phone_number, o.delivery_type, o.note, o.created_at,
                   u.full_name, u.username
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.user_id
            WHERE o.status = $1
            ORDER BY o.created_at DESC LIMIT $2 OFFSET $3
        """, status, limit, offset)
    else:
        rows = await _query("""
            SELECT o.id, o.user_id, o.total_amount, o.status, o.delivery_address,
                   o.phone_number, o.delivery_type, o.note, o.created_at,
                   u.full_name, u.username
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.user_id
            ORDER BY o.created_at DESC LIMIT $1 OFFSET $2
        """, limit, offset)

    total = await _fetchval("SELECT COUNT(*) FROM orders") or 0

    result = []
    for r in rows:
        r["status_label"] = STATUS_LABELS.get(r.get("status") or "pending", r.get("status", ""))
        r["created_at"] = str(r.get("created_at", ""))[:16]
        result.append(r)
    return {"orders": result, "total": total}


@app.get("/api/orders/{order_id}")
async def get_order_detail(order_id: int):
    rows = await _query("""
        SELECT o.*, u.full_name, u.username, u.phone_number as user_phone
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.id = $1
    """, order_id)
    if not rows:
        raise HTTPException(404, "Buyurtma topilmadi")
    order = rows[0]

    items = await _query("""
        SELECT oi.quantity, oi.price_at_time, p.name
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = $1
    """, order_id)

    order["items"] = items
    order["status_label"] = STATUS_LABELS.get(order.get("status") or "pending", "")
    order["created_at"] = str(order.get("created_at", ""))[:16]
    return order


@app.patch("/api/orders/{order_id}/status")
async def update_order_status(order_id: int, body: StatusUpdate):
    valid = ["pending", "preparing", "delivering", "completed", "cancelled"]
    if body.status not in valid:
        raise HTTPException(400, f"Noto'g'ri status. Mumkin: {valid}")
    await _execute("UPDATE orders SET status = $1 WHERE id = $2", body.status, order_id)
    return {"success": True, "status": body.status, "label": STATUS_LABELS.get(body.status, body.status)}


# ── API: Mahsulotlar ──────────────────────────────────────────────────

@app.get("/api/products")
async def get_products(category_id: Optional[int] = None):
    if category_id:
        rows = await _query("""
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.category_id = $1
            ORDER BY p.id
        """, category_id)
    else:
        rows = await _query("""
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY c.id, p.id
        """)
    return rows


@app.patch("/api/products/{product_id}")
async def update_product(product_id: int, body: ProductUpdate):
    updates = {}
    if body.name is not None: updates["name"] = body.name
    if body.price is not None: updates["price"] = body.price
    if body.description is not None: updates["description"] = body.description
    if body.is_active is not None: updates["is_active"] = body.is_active

    if not updates:
        raise HTTPException(400, "Hech narsa o'zgartirilmadi")

    # Dynamic query build
    set_parts = [f"{k} = ${i+2}" for i, k in enumerate(updates.keys())]
    sql = f"UPDATE products SET {', '.join(set_parts)} WHERE id = $1"
    await _execute(sql, product_id, *updates.values())
    return {"success": True}


# ── API: Kategoriyalar ────────────────────────────────────────────────

@app.get("/api/categories")
async def get_categories():
    return await _query("SELECT * FROM categories ORDER BY id")


# ── API: Foydalanuvchilar ─────────────────────────────────────────────

@app.get("/api/users")
async def get_users(limit: int = Query(20, ge=1, le=100), offset: int = 0):
    rows = await _query("""
        SELECT u.*, 
               (SELECT COUNT(*) FROM orders WHERE user_id = u.user_id) as orders_count
        FROM users u
        ORDER BY u.created_at DESC
        LIMIT $1 OFFSET $2
    """, limit, offset)
    total = await _fetchval("SELECT COUNT(*) FROM users") or 0
    return {"users": rows, "total": total}


# ── API: Top mahsulotlar ──────────────────────────────────────────────

@app.get("/api/top-products")
async def get_top_products(limit: int = 10):
    return await _query("""
        SELECT p.name, SUM(oi.quantity) as total_qty, SUM(oi.quantity * oi.price_at_time) as total_revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        GROUP BY p.id, p.name
        ORDER BY total_qty DESC
        LIMIT $1
    """, limit)


# ── Sog'liq tekshiruvi ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/")
async def root():
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Fast Food Admin API v2.0", "docs": "/docs"}
