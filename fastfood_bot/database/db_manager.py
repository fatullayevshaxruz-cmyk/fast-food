"""
db_manager.py
-------------
Dinamik menyu tizimi uchun SQLite operatsiyalari.
Bu modul faqat 'dynamic_menu' jadvalini boshqaradi,
mavjud PostgreSQL/asyncpg jadvallariga tegmaydi.
"""

import aiosqlite
import logging
import os
from typing import Optional, List

# SQLite fayli database/ papkasida saqlanadi
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "dynamic_menu.db")


# ─────────────────────────────────────────────
# Jadval yaratish (bot ishga tushganda chaqiriladi)
# ─────────────────────────────────────────────


# Jadval bo'sh bo'lganda qo'shiladigan standart taomlar
_DEFAULT_ITEMS = [
    ("Classic Burger",      25000, "Mol go'shti kotleti, bodring, pomidor, ketchup, mayonez."),
    ("Cheeseburger",        28000, "Cheddar pishloq, mol go'shti, salat bargi, maxsus sous."),
    ("Double Burger",       45000, "Ikkita kotlet, ikki qavat pishloq, maxsus sous."),
    ("Chicken Burger",      32000, "Qovurilgan tovuq go'shti, coleslaw, ranch sousi."),
    ("Pepperoni Pizza",     65000, "Klassik pepperoni, motsarella, tomat sousi."),
    ("Margarita Pizza",     55000, "Pomidor, rayhon, motsarella pishloqi."),
    ("Tovuqli Lavash",      28000, "Tovuq go'shti, chips, yangi sabzavotlar, garmdori sousi."),
    ("Mol go'shtli Lavash", 30000, "Mol go'shti, chips, bodring, pomidor, mayonez, ketchup."),
    ("Tovuqli Doner",       32000, "Grillda pishirilgan tovuq go'shti, sabzavot, yogurt sousi."),
    ("Kartoshka Fri",       12000, "Qovurilgan kartoshka, ketchup yoki sous bilan."),
    ("Nuggets (6 dona)",    18000, "Tovuq nuggets, dipping sous bilan."),
    ("Coca Cola 0.5L",       8000, "Muzdek Coca-Cola."),
    ("Milkshake",           18000, "Muzqaymoqli sut kokteyli — shokolad, vanil yoki qulupnay."),
    ("Burger Kombo",        45000, "Classic Burger + Kartoshka Fri + Coca Cola 0.5L."),
    ("Cheesecake",          22000, "Klassik limonli cheesecake, meva sousi bilan."),
]


async def init_dynamic_menu_db() -> None:
    """
    dynamic_menu jadvalini yaratadi.
    Jadval yangi va bo'sh bo'lsa standart taomlar bilan to'ldiradi.
    """
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dynamic_menu (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                price       INTEGER NOT NULL,
                description TEXT    DEFAULT '',
                name_ru     TEXT,
                name_en     TEXT,
                description_ru TEXT,
                description_en TEXT
            )
        """)
        await db.commit()

        # Ko'p tilli ustunlarni mavjud jadvallarga qo'shish (migration)
        for col, ctype in [
            ("name_ru", "TEXT"),
            ("name_en", "TEXT"),
            ("description_ru", "TEXT"),
            ("description_en", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE dynamic_menu ADD COLUMN {col} {ctype}")
                await db.commit()
            except Exception:
                pass  # Ustun allaqachon mavjud

        # Bo'sh bo'lsa standart taomlar bilan to'ldirish
        cursor = await db.execute("SELECT COUNT(*) FROM dynamic_menu")
        row = await cursor.fetchone()
        count = row[0] if row else 0

        if count == 0:
            await db.executemany(
                "INSERT INTO dynamic_menu (name, price, description) VALUES (?, ?, ?)",
                _DEFAULT_ITEMS
            )
            await db.commit()
            logging.info(f"dynamic_menu: {len(_DEFAULT_ITEMS)} ta standart taom qo'shildi.")

    logging.info("dynamic_menu jadvali tayyor.")


# ─────────────────────────────────────────────
# CRUD funksiyalari
# ─────────────────────────────────────────────

async def dm_add_item(name: str, price: int, description: str = "",
                      name_ru: str = None, name_en: str = None,
                      description_ru: str = None, description_en: str = None) -> int:
    """
    Yangi taom qo'shadi — ko'p tilli ma'lumotlar bilan.
    Qaytaradi: yangi qator id si.
    """
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO dynamic_menu
               (name, price, description, name_ru, name_en, description_ru, description_en)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, price, description,
             name_ru or None, name_en or None,
             description_ru or None, description_en or None)
        )
        await db.commit()
        return cursor.lastrowid


async def dm_get_all_items() -> List[dict]:
    """Barcha taomlarni qaytaradi (barcha ustunlar)."""
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, price, description, name_ru, name_en, description_ru, description_en FROM dynamic_menu ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def dm_get_item_by_id(item_id: int) -> Optional[dict]:
    """Berilgan id bo'yicha taomni qaytaradi (barcha ustunlar)."""
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, price, description, name_ru, name_en, description_ru, description_en FROM dynamic_menu WHERE id = ?",
            (item_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None



async def dm_update_price(item_id: int, new_price: int) -> bool:
    """
    Taom narxini yangilaydi.
    Qaytaradi: True — muvaffaqiyatli, False — taom topilmadi.
    """
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE dynamic_menu SET price = ? WHERE id = ?",
            (new_price, item_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def dm_delete_item(item_id: int) -> bool:
    """
    Taomni o'chiradi.
    Qaytaradi: True — muvaffaqiyatli, False — taom topilmadi.
    """
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM dynamic_menu WHERE id = ?",
            (item_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


# ─────────────────────────────────────────────
# Formatlash yordamchi funksiyasi
# ─────────────────────────────────────────────

def format_menu_text(items: List[dict]) -> str:
    """Taomlar ro'yxatini chiroyli HTML matn ko'rinishiga o'tkazadi."""
    if not items:
        return "🍽 Hozircha dinamik menyu bo'sh.\nAdmin yangi taom qo'shishi mumkin."

    lines = ["🍽 <b>Dinamik Menyu</b>\n"]
    for item in items:
        desc = f"\n   <i>{item['description']}</i>" if item['description'] else ""
        lines.append(
            f"• <b>{item['name']}</b>{desc}\n"
            f"   💰 Narxi: <b>{item['price']:,} so'm</b>\n"
        )
    lines.append("✅ Narxlar doim yangilangan!")
    return "\n".join(lines)
