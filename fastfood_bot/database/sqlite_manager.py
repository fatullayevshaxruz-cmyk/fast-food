import aiosqlite
import re

class SQLitePool:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None

    async def init(self):
        pass # aiosqlite connects per query or we can keep one connection? 
        # aiosqlite typically used with 'async with connect...'
        # But we need to mimic a pool that can be acquired.
        pass

    def acquire(self):
        return SQLiteConnectionContext(self.db_path)

    async def close(self):
        pass

    async def fetchval(self, query, *args):
        async with SQLiteConnectionContext(self.db_path) as conn:
            return await conn.fetchval(query, *args)
            
    async def fetch(self, query, *args):
        async with SQLiteConnectionContext(self.db_path) as conn:
            return await conn.fetch(query, *args)

class SQLiteConnectionContext:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

    async def __aenter__(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        return SQLiteConnection(self.conn)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            await self.conn.close()

class SQLiteConnection:
    def __init__(self, conn):
        self.conn = conn

    def _convert_query(self, query):
        # Convert $1, $2... to ?
        # Handle "ON CONFLICT" since sqlite uses "ON CONFLICT" differently or "INSERT OR REPLACE"
        # Ideally we'd need more complex logic.
        # But for this simple bot:
        # 1. users table: INSERT ... ON CONFLICT (...) DO UPDATE ...
        # SQLite: INSERT OR REPLACE INTO ... (if unique key matches)
        # OR: INSERT INTO ... ON CONFLICT(...) DO UPDATE SET ... (SQLite 3.24+)
        
        # Replace $num with ?
        new_query = re.sub(r'\$\d+', '?', query)
        
        # Fix Serial types in create table? No, they are text in queries so it's fine.
        # But schema creation queries use SERIAL, which sqlite doesn't like (uses INTEGER PRIMARY KEY AUTOINCREMENT).
        # We might need to handle schema creation separately.
        return new_query

    async def execute(self, query, *args):
        q = self._convert_query(query)
        # Handle SERIAL -> INTEGER PRIMARY KEY replacement for Create Table
        if "SERIAL PRIMARY KEY" in q:
            q = q.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        
        # Handle integer cast
        if "::integer" in q:
            q = q.replace("::integer", "")
            
        try:
            await self.conn.execute(q, args)
            await self.conn.commit()
        except Exception as e:
            # Ignore some specific sqlite errors if needed?
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

