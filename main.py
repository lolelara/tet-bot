from database import db
from telegram_client import TelegramBot
import asyncio
import os

# Appwrite Function Entry Point
# context.req and context.res are available
def main(context):
    # This function is designed to be called by a CRON job
    # Appwrite passes context object
    
    print("Checking for due schedules...")
    
    # Since Appwrite functions are synchronous by default in some runtimes or async in others,
    # we'll wrap the async logic.
    # Assuming Python 3.9+ runtime which supports async, but the entry point 'main' 
    # might need to be synchronous that calls async.
    
    try:
        asyncio.run(process_schedules())
        return context.res.json({
            'status': 'success',
            'message': 'Schedules processed'
        })
    except Exception as e:
        context.error(str(e))
        return context.res.json({
            'status': 'error',
            'message': str(e)
        }, 500)

async def process_schedules():
    due_schedules = db.get_due_schedules()
    
    if not due_schedules:
        print("No schedules due.")
        return

    print(f"Found {len(due_schedules)} due schedules.")
    
    for schedule in due_schedules:
        user = db.get_user(schedule['user_phone'])
        if not user or not user.get('session_string'):
            print(f"User {schedule['user_phone']} not found or invalid session.")
            continue

        bot = TelegramBot(user['session_string'])
        
        for chat_id in schedule['groups']:
            try:
                print(f"Sending message to {chat_id} for user {user['phone']}")
                await bot.send_message(chat_id, schedule['message'])
            except Exception as e:
                print(f"Failed to send to {chat_id}: {e}")
        
        # Update last run time
        db.update_last_run(schedule['id'])
