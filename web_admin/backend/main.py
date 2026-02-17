from fastapi import FastAPI
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fastfood_bot")
POSTGRES_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

@app.on_event("startup")
async def startup():
    app.state.pool = await asyncpg.create_pool(POSTGRES_URI)

@app.on_event("shutdown")
async def shutdown():
    await app.state.pool.close()

@app.get("/api/stats")
async def get_stats():
    async with app.state.pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        orders = await conn.fetchval("SELECT COUNT(*) FROM orders")
        revenue = await conn.fetchval("SELECT SUM(total_amount) FROM orders WHERE status = 'delivered'") or 0
    return {"users": users, "orders": orders, "revenue": revenue}

@app.get("/api/orders")
async def get_orders(limit: int = 10):
    async with app.state.pool.acquire() as conn:
        orders = await conn.fetch("""
            SELECT id, user_id, total_amount, status, created_at 
            FROM orders 
            ORDER BY created_at DESC 
            LIMIT $1
        """, limit)
    return [dict(record) for record in orders]
