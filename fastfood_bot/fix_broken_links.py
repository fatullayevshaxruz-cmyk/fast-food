import asyncio
import aiosqlite
import os

DB_NAME = "database.db"

# New URLs to replace broken ones
UPDATES = [
    (5, "https://www.themealdb.com/images/media/meals/kcv6hj1598733479.jpg"), # Tovuqli Lavash
    (14, "https://loremflickr.com/500/500/hotdog,cheese/all"), # Pishloqli Hot-Dog
    (15, "https://loremflickr.com/500/500/hotdog/all"), # Double Hot-Dog
    (16, "https://loremflickr.com/500/500/frenchfries/all"), # Fri Kartoshkasi
    (18, "https://www.themealdb.com/images/media/meals/1550441882.jpg"), # Derevenskiy Kartoshka
    (19, "https://www.themealdb.com/images/media/meals/04axct1763793018.jpg"), # Mol go'shtli Doner
    (20, "https://www.themealdb.com/images/media/meals/prjve31763486864.jpg"), # Tovuqli Doner
    (25, "https://loremflickr.com/500/500/burger,fries/all"), # Student Kombo
    (26, "https://loremflickr.com/500/500/fastfood,feast/all"), # Family Kombo
]

async def fix_broken_links():
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
    asyncio.run(fix_broken_links())
