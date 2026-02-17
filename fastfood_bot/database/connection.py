import asyncpg
import logging
from config import POSTGRES_URI
from .sqlite_manager import SQLitePool

db_pool = None

async def create_db_pool():
    try:
        return await asyncpg.create_pool(POSTGRES_URI)
    except Exception as e:
        logging.warning(f"PostgreSQL connection failed: {e}. Switching to SQLite.")
        pool = SQLitePool("database.db")
        await pool.init()
        return pool

async def init_db_pool():
    global db_pool
    db_pool = await create_db_pool()

async def get_db_pool():
    global db_pool
    if not db_pool:
        await init_db_pool()
    return db_pool

async def close_db_pool():
    global db_pool
    if db_pool:
        await db_pool.close()

