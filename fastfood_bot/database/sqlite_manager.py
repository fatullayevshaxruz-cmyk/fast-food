import aiosqlite
import re


class SQLitePool:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        # ── Tezlik optimizatsiyasi ──────────────────────────────
        await self._conn.execute("PRAGMA journal_mode=WAL")      # WAL — yozish tezroq
        await self._conn.execute("PRAGMA synchronous=NORMAL")     # Normal sync
        await self._conn.execute("PRAGMA cache_size=-16000")      # 16MB kesh
        await self._conn.execute("PRAGMA temp_store=MEMORY")      # Temp RAM da
        await self._conn.execute("PRAGMA mmap_size=134217728")    # 128MB memory-mapped I/O
        await self._conn.execute("PRAGMA busy_timeout=5000")      # Lock bo'lsa 5s kutadi
        await self._conn.execute("PRAGMA foreign_keys=ON")        # FK tekshiruvi
        # ── Tez qidiruv uchun indekslar ───────────────────────────
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_cart_user   ON cart_items(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_stat ON orders(status)",
            "CREATE INDEX IF NOT EXISTS idx_oi_order    ON order_items(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_prod_cat    ON products(category_id, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_fav_user    ON favorites(user_id)",
        ]:
            try:
                await self._conn.execute(idx_sql)
            except Exception:
                pass
        await self._conn.commit()

    def acquire(self):
        return SQLiteConnectionContext(self._conn)

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def fetchval(self, query, *args):
        """Pool darajasida fetchval — to'g'ridan-to'g'ri connection orqali."""
        conn = SQLiteConnection(self._conn)
        return await conn.fetchval(query, *args)
            
    async def fetch(self, query, *args):
        """Pool darajasida fetch — to'g'ridan-to'g'ri connection orqali."""
        conn = SQLiteConnection(self._conn)
        return await conn.fetch(query, *args)


class SQLiteConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return SQLiteConnection(self.conn)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class SQLiteConnection:
    def __init__(self, conn):
        self.conn = conn

    def _convert_query(self, query):
        new_query = re.sub(r'\$\d+', '?', query)
        return new_query

    async def execute(self, query, *args):
        q = self._convert_query(query)
        if "SERIAL PRIMARY KEY" in q:
            q = q.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        if "::integer" in q:
            q = q.replace("::integer", "")
        try:
            await self.conn.execute(q, args)
            await self.conn.commit()
        except Exception as e:
            raise e

    async def fetch(self, query, *args):
        q = self._convert_query(query)
        cursor = await self.conn.execute(q, args)
        try:
            rows = await cursor.fetchall()
            return rows
        finally:
            await cursor.close()

    async def fetchrow(self, query, *args):
        q = self._convert_query(query)
        
        # Handle RETURNING id emulation for SQLite
        if 'returning id' in q.lower():
            q = re.sub(r'RETURNING\s+id', '', q, flags=re.IGNORECASE).strip()
            cursor = await self.conn.execute(q, args)
            try:
                await self.conn.commit()
                last_id = cursor.lastrowid
                return {'id': last_id}
            finally:
                await cursor.close()
        
        # Normal fetchrow
        cursor = await self.conn.execute(q, args)
        try:
            row = await cursor.fetchone()
            return row
        finally:
            await cursor.close()
            
    async def fetchval(self, query, *args):
        row = await self.fetchrow(query, *args)
        if row:
             return row[0]
        return None
    
    def transaction(self):
        return TransactionContext(self.conn)


class TransactionContext:
    def __init__(self, conn):
        self.conn = conn
        
    async def __aenter__(self):
        pass 

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.conn.rollback()
        else:
            await self.conn.commit()
