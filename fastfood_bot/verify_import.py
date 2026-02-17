
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Verifying imports...")

try:
    from bot import dp
    from handlers import menu, order, cart, admin, start
    print("Handlers imported successfully.")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

print("Verifying Keyboards...")
try:
    from keyboards import product_keyboard
    # Test generation
    markup = product_keyboard.get_product_markup(1, 1, 0, 5, 1)
    print("Keyboards generated successfully.")
except Exception as e:
    print(f"Keyboard Error: {e}")
    sys.exit(1)

print("Verification passed!")
