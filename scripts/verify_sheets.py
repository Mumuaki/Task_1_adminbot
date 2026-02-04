import asyncio
import sys
import os

# Add project root to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from loguru import logger
from src.storage.sheets import GoogleSheetsManager
from config.settings import settings

async def verify():
    # Configure logger to print to stdout
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    print("--- Google Sheets Verification ---")
    
    if not settings:
        logger.error("Settings failed to load.")
        return

    print(f"Spreadsheet ID: {settings.google_sheets.spreadsheet_id}")
    print(f"Service Account Path: {settings.google_sheets.service_account_path}")
    
    if not settings.google_sheets.service_account_path.exists():
         logger.error(f"Service account file not found at: {settings.google_sheets.service_account_path}")
         return

    manager = GoogleSheetsManager(
        spreadsheet_id=settings.google_sheets.spreadsheet_id,
        service_account_path=settings.google_sheets.service_account_path
    )

    print("\n1. Testing Connection & Whitelist...")
    try:
        ss = await manager._get_spreadsheet()
        worksheet = await ss.worksheet("Конфигурация")
        all_values = await worksheet.get_all_values()
        
        print(f"DEBUG: Total rows found: {len(all_values)}")
        if all_values:
            print(f"DEBUG: Header row: {all_values[0]}")
            if len(all_values) > 1:
                print(f"DEBUG: First data row: {all_values[1]}")
        
        whitelist = await manager.get_whitelist()
        print(f"SUCCESS: Loaded whitelist for {len(whitelist)} chats.")
        for chat_id, users in whitelist.items():
            print(f"  - Chat {chat_id}: {len(users)} allowed users")
    except Exception as e:
        print(f"ERROR reading whitelist: {e}")

    print("\n2. Testing Monitored Chats...")
    try:
        chats = await manager.get_monitored_chats()
        print(f"SUCCESS: Loaded {len(chats)} monitored chats.")
        for chat_id, name in chats:
            print(f"  - [{chat_id}] {name}")
    except Exception as e:
        print(f"ERROR reading monitored chats: {e}")

if __name__ == "__main__":
    # Windows/Python 3.8+ compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(verify())
