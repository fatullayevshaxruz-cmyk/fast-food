import asyncio
import aiosqlite
import os

DB_NAME = "database.db"

# Correct JPG URLs from seed.py
UPDATES = [
    (4, "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=500"), # Mol go'shtli Lavash
    (5, "https://images.unsplash.com/photo-1529042410759-befb1204b465?w=500"), # Tovuqli Lavash
    (6, "https://images.unsplash.com/photo-1561651823-34feb02250e4?w=500"), # Mini Lavash
]

async def fix_images():
    if not os.path.exists(DB_NAME):
        print(f"Error: {DB_NAME} not found.")
        return

    print(f"Connecting to {DB_NAME}...")
    async with aiosqlite.connect(DB_NAME) as db:
        for pid, new_url in UPDATES:
            print(f"Updating product ID {pid}...")
            await db.execute("UPDATE products SET image_url = ? WHERE id = ?", (new_url, pid))
        
        await db.commit()
        print("Database updated successfully.")

if __name__ == "__main__":
    asyncio.run(fix_images())
