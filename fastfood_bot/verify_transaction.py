
import asyncio
import os
from database.sqlite_manager import SQLitePool

async def test_transaction():
    print("Testing SQLite Transaction...")
    try:
        pool = SQLitePool("test_db.db")
        # Initialize (mocking init)
        
        async with pool.acquire() as conn:
            print("Acquired connection.")
            try:
                async with conn.transaction():
                    print("Entered transaction context successfully.")
                    await conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")
                    await conn.execute("INSERT INTO test (id) VALUES (1)")
                print("Exited transaction context.")
            except AttributeError as e:
                print(f"FAILED: AttributeError: {e}")
                return
            except Exception as e:
                print(f"FAILED: {e}")
                return
                
        print("TEST PASSED!")
    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        if os.path.exists("test_db.db"):
            os.remove("test_db.db")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_transaction())
