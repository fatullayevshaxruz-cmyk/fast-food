import asyncio
import aiosqlite
import os

DB_NAME = "database.db"

async def verify_content():
    if not os.path.exists(DB_NAME):
        print(f"Error: {DB_NAME} not found.")
        return

    print(f"Connecting to {DB_NAME}...")
    async with aiosqlite.connect(DB_NAME) as db:
        print("\n--- CATEGORIES ---")
        async with db.execute("SELECT id, name, emoji FROM categories") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                print(row)

        print("\n--- PRODUCTS ---")
        async with db.execute("SELECT id, category_id, name, image_url FROM products") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                pid, cid, name, img = row
                status = "OK" if img else "MISSING"
                print(f"[{cid}] {name} (ID: {pid}): {img} [{status}]")

if __name__ == "__main__":
    asyncio.run(verify_content())
