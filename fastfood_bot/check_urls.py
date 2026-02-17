import asyncio
import aiosqlite
import aiohttp
import os

DB_NAME = "database.db"

async def check_urls():
    if not os.path.exists(DB_NAME):
        print(f"Error: {DB_NAME} not found.")
        return

    print(f"Checking images in {DB_NAME}...")
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name, image_url FROM products") as cursor:
            rows = await cursor.fetchall()
            
    async with aiohttp.ClientSession() as session:
        for pid, name, url in rows:
            if not url:
                print(f"[MISSING] ID: {pid} {name}")
                continue
                
            try:
                async with session.head(url, timeout=5) as resp:
                    content_type = resp.headers.get('Content-Type', 'Unknown')
                    print(f"[{resp.status}] ID: {pid} {name} - {content_type}")
            except Exception as e:
                print(f"[ERROR] ID: {pid} {name} - {e}")

if __name__ == "__main__":
    asyncio.run(check_urls())
