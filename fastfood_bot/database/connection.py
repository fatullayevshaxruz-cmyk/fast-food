import asyncpg
import logging
import os
from config import POSTGRES_URI
from .sqlite_manager import SQLitePool

db_pool = None

# SQLite fayli bot papkasida saqlanadi
_DB_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(_DB_DIR, "fastfood.db")

async def create_db_pool():
    try:
        pool = await asyncpg.create_pool(POSTGRES_URI)
        logging.info("PostgreSQL ga ulandi.")
        return pool
    except Exception as e:
        logging.warning(f"PostgreSQL connection failed: {e}. Switching to SQLite.")
        pool = SQLitePool(SQLITE_PATH)
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

