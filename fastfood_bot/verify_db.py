import asyncio
import aiosqlite
import os

DB_NAME = "database.db"

async def verify_products():
    if not os.path.exists(DB_NAME):
        print(f"Error: {DB_NAME} not found.")
        return

    print(f"Connecting to {DB_NAME}...")
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name, image_url FROM products") as cursor:
            rows = await cursor.fetchall()
            print(f"Found {len(rows)} products:")
            for row in rows:
                pid, name, img = row
                status = "OK" if img else "MISSING"
                print(f"ID: {pid}, Name: {name}, Image: {img} [{status}]")

if __name__ == "__main__":
    asyncio.run(verify_products())
