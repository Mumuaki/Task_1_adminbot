import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telethon import TelegramClient
from config.settings import settings

async def resolve_username(username: str):
    print(f"Connecting to Telegram...")
    
    if not settings:
        print("Error: Settings not loaded.")
        return

    client = TelegramClient(
        settings.telethon.session_path,
        settings.telethon.api_id,
        settings.telethon.api_hash
    )
    
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Client not authorized. Please run the main bot first or authorize interactively.")
        return

    try:
        print(f"Resolving {username}...")
        entity = await client.get_entity(username)
        print(f"\nSUCCESS! Found entity:")
        print(f"Title/Name: {getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown'))}")
        print(f"ID: {entity.id}")
        
        # Telethon IDs for channels/groups might need -100 prefix for other libraries like aiogram
        # entity.id is usually positive integer for Telethon, but for API usage (bot API) it might differ.
        # Channels usually start with 100... in Telethon which maps to -100... in Bot API.
        
        bot_api_id = int(f"-100{entity.id}") if getattr(entity, 'broadcast', False) or getattr(entity, 'megagroup', False) else entity.id
        # Note: This is a rough heuristic. 
        # Better: use proper utils. But for now verify both.
        
        print(f"Possible ID for config (try this first): -100{entity.id}")
        print(f"Raw Telethon ID: {entity.id}")
        
    except Exception as e:
        print(f"Error resolving username: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        username = input("Enter username (e.g. @groupname): ")
    else:
        username = sys.argv[1]
        
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(resolve_username(username))
