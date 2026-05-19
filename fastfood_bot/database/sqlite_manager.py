import aiosqlite
import re


class SQLitePool:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        # ── Tezlik optimizatsiyasi ────────────────────────────────
        await self._conn.execute("PRAGMA journal_mode=WAL")      # WAL — yozish tezroq
        await self._conn.execute("PRAGMA synchronous=NORMAL")     # Normal sync — xavfsiz + tez
        await self._conn.execute("PRAGMA cache_size=-8000")       # 8MB kesh
        await self._conn.execute("PRAGMA temp_store=MEMORY")      # Temp ma'lumotlar RAM da
        await self._conn.execute("PRAGMA mmap_size=67108864")     # 64MB memory-mapped I/O
        await self._conn.commit()

    def acquire(self):
        return SQLiteConnectionContext(self._conn)

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def fetchval(self, query, *args):
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)
            
    async def fetch(self, query, *args):
        async with self.acquire() as conn:
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
