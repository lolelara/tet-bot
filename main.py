from database import db
from telegram_client import TelegramBot
import json
import asyncio
import os

# Helper to parse request body
def get_json(context):
    try:
        return json.loads(context.req.body)
    except:
        return {}

# Appwrite Function Entry Point
def main(context):
    # Enable CORS
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }

    if context.req.method == 'OPTIONS':
        return context.res.json({'status': 'ok'}, 200, headers)

    path = context.req.path
    method = context.req.method

    print(f"Request: {method} {path}")

    try:
        # 1. CRON Job (Scheduler)
        # Appwrite CRON requests usually have a specific header or path, 
        # but we can also dedicate a path like /cron
        if path == '/cron' or path == '/':
            # Default path might be used by CRON if not specified
            return asyncio.run(run_scheduler(context, headers))

        # 2. Auth: Send Code
        if path == '/auth/send_code' and method == 'POST':
            return asyncio.run(handle_send_code(context, headers))

        # 3. Auth: Verify Code
        if path == '/auth/verify_code' and method == 'POST':
            return asyncio.run(handle_verify_code(context, headers))

        # 4. Get Groups
        if path == '/groups' and method == 'POST':
            # We expect session_string in body for statelessness
            return asyncio.run(handle_get_groups(context, headers))

        # 5. Create Schedule
        if path == '/schedule' and method == 'POST':
            return handle_create_schedule(context, headers)

        # 6. Get Schedules
        if path == '/schedules' and method == 'POST':
            return handle_get_schedules(context, headers)

        return context.res.json({'error': 'Not Found'}, 404, headers)

    except Exception as e:
        context.error(str(e))
        return context.res.json({'error': str(e)}, 500, headers)

# --- Handlers ---

async def run_scheduler(context, headers):
    print("Running Scheduler...")
    due_schedules = db.get_due_schedules()
    results = []
    
    for schedule in due_schedules:
        user = db.get_user(schedule['user_phone'])
        if not user or not user.get('session_string'):
            continue

        bot = TelegramBot(user['session_string'])
        for chat_id in schedule['groups']:
            try:
                await bot.send_message(chat_id, schedule['message'])
                results.append(f"Sent to {chat_id}")
            except Exception as e:
                results.append(f"Failed {chat_id}: {e}")
        
        db.update_last_run(schedule['$id']) # Use $id for Appwrite doc ID

    return context.res.json({'status': 'success', 'results': results}, 200, headers)

async def handle_send_code(context, headers):
    data = get_json(context)
    phone = data.get('phone')
    bot = TelegramBot()
    phone_code_hash = await bot.send_code(phone)
    return context.res.json({'status': 'success', 'phone_code_hash': phone_code_hash}, 200, headers)

async def handle_verify_code(context, headers):
    data = get_json(context)
    phone = data.get('phone')
    code = data.get('code')
    phone_code_hash = data.get('phone_code_hash')
    
    bot = TelegramBot()
    session_string = await bot.verify_code(phone, phone_code_hash, code)
    
    # Save user to DB
    db.save_user(phone, session_string)
    
    return context.res.json({'status': 'success', 'session_string': session_string, 'phone': phone}, 200, headers)

async def handle_get_groups(context, headers):
    data = get_json(context)
    session_string = data.get('session_string')
    
    if not session_string:
        return context.res.json({'error': 'Unauthorized'}, 401, headers)

    bot = TelegramBot(session_string)
    groups = await bot.get_groups()
    return context.res.json({'status': 'success', 'groups': groups}, 200, headers)

def handle_create_schedule(context, headers):
    data = get_json(context)
    user_phone = data.get('user_phone')
    message = data.get('message')
    groups = data.get('groups')
    interval = int(data.get('interval'))
    
    db.add_schedule(user_phone, message, groups, interval)
    return context.res.json({'status': 'success'}, 200, headers)

def handle_get_schedules(context, headers):
    data = get_json(context)
    user_phone = data.get('user_phone')
    schedules = db.get_user_schedules(user_phone)
    return context.res.json({'status': 'success', 'schedules': schedules}, 200, headers)
