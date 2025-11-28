import json
import asyncio
import os
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid

load_dotenv()

# --- Environment Variables ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT")
APPWRITE_PROJECT_ID = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("DATABASE_ID", "telegram_bot_db")
USERS_COLLECTION_ID = os.environ.get("USERS_COLLECTION_ID", "users")
SCHEDULES_COLLECTION_ID = os.environ.get("SCHEDULES_COLLECTION_ID", "schedules")

# --- Telegram Client (Embedded) ---

class TelegramBot:
    def __init__(self, session_string: str = None):
        self.session_string = session_string
        self.client = None

    async def connect(self):
        if not self.session_string:
            self.client = Client(":memory:", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        else:
            self.client = Client("user_session", session_string=self.session_string, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        
        await self.client.connect()

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()

    async def send_code(self, phone_number: str):
        await self.connect()
        try:
            sent_code = await self.client.send_code(phone_number)
            return sent_code.phone_code_hash
        except Exception as e:
            await self.disconnect()
            raise e

    async def verify_code(self, phone_number: str, phone_code_hash: str, code: str):
        await self.connect()
        try:
            await self.client.sign_in(phone_number, phone_code_hash, code)
            session_string = await self.client.export_session_string()
            await self.disconnect()
            return session_string
        except SessionPasswordNeeded:
            await self.disconnect()
            raise Exception("2FA_REQUIRED")
        except Exception as e:
            await self.disconnect()
            raise e

    async def get_groups(self) -> List[Dict]:
        await self.connect()
        groups = []
        async for dialog in self.client.get_dialogs():
            if dialog.chat.type.value in ["group", "supergroup"]:
                groups.append({
                    "id": dialog.chat.id,
                    "title": dialog.chat.title
                })
        await self.disconnect()
        return groups

    async def send_message(self, chat_id: int, text: str):
        await self.connect()
        try:
            await self.client.send_message(chat_id, text)
        finally:
            await self.disconnect()

# --- Database Logic (Embedded) ---

class LocalDatabase:
    def __init__(self):
        self.file = '/tmp/db.json'
        self._load()

    def _load(self):
        if not os.path.exists(self.file):
            self.data = {"users": [], "schedules": []}
            self._save()
        else:
            with open(self.file, 'r') as f:
                self.data = json.load(f)

    def _save(self):
        with open(self.file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get_user(self, phone: str) -> Optional[Dict]:
        for user in self.data["users"]:
            if user["phone"] == phone:
                return user
        return None

    def save_user(self, phone: str, session_string: str, role: str = "subscriber"):
        user = self.get_user(phone)
        if user:
            user["session_string"] = session_string
        else:
            self.data["users"].append({
                "phone": phone,
                "session_string": session_string,
                "role": role,
                "is_active": True
            })
        self._save()
    
    def update_user_status(self, phone: str, is_active: bool):
        user = self.get_user(phone)
        if user:
            user["is_active"] = is_active
            self._save()
            return True
        return False

    def get_all_users(self) -> List[Dict]:
        return self.data["users"]

    def add_schedule(self, user_phone: str, message: str, groups: List[int], interval_minutes: int):
        self.data["schedules"].append({
            "id": str(int(time.time() * 1000)),
            "user_phone": user_phone,
            "message": message,
            "groups": groups,
            "interval_minutes": interval_minutes,
            "last_run": 0
        })
        self._save()

    def get_user_schedules(self, user_phone: str) -> List[Dict]:
        return [s for s in self.data["schedules"] if s["user_phone"] == user_phone]

    def get_due_schedules(self) -> List[Dict]:
        now = time.time()
        due = []
        for schedule in self.data["schedules"]:
            if now - schedule["last_run"] >= schedule["interval_minutes"] * 60:
                due.append(schedule)
        return due

    def update_last_run(self, schedule_id: str):
        for schedule in self.data["schedules"]:
            if schedule["id"] == schedule_id:
                schedule["last_run"] = time.time()
                break
        self._save()

class AppwriteDatabase:
    def __init__(self):
        from appwrite.client import Client
        from appwrite.services.databases import Databases
        from appwrite.query import Query
        
        self.client = Client()
        self.client.set_endpoint(APPWRITE_ENDPOINT)
        self.client.set_project(APPWRITE_PROJECT_ID)
        self.client.set_key(APPWRITE_API_KEY)
        self.databases = Databases(self.client)
        self.Query = Query

    def get_user(self, phone: str) -> Optional[Dict]:
        try:
            result = self.databases.list_documents(
                DATABASE_ID,
                USERS_COLLECTION_ID,
                [self.Query.equal("phone", phone)]
            )
            if result['documents']:
                return result['documents'][0]
            return None
        except Exception as e:
            print(f"Appwrite Error: {e}")
            return None

    def save_user(self, phone: str, session_string: str, role: str = "subscriber"):
        user = self.get_user(phone)
        if user:
            self.databases.update_document(
                DATABASE_ID,
                USERS_COLLECTION_ID,
                user['$id'],
                {"session_string": session_string}
            )
        else:
            self.databases.create_document(
                DATABASE_ID,
                USERS_COLLECTION_ID,
                'unique()',
                {
                    "phone": phone,
                    "session_string": session_string,
                    "role": role,
                    "is_active": True
                }
            )

    def update_user_status(self, phone: str, is_active: bool):
        user = self.get_user(phone)
        if user:
            self.databases.update_document(
                DATABASE_ID,
                USERS_COLLECTION_ID,
                user['$id'],
                {"is_active": is_active}
            )
            return True
        return False

    def get_all_users(self) -> List[Dict]:
        try:
            result = self.databases.list_documents(DATABASE_ID, USERS_COLLECTION_ID)
            return result['documents']
        except:
            return []

    def add_schedule(self, user_phone: str, message: str, groups: List[int], interval_minutes: int):
        self.databases.create_document(
            DATABASE_ID,
            SCHEDULES_COLLECTION_ID,
            'unique()',
            {
                "user_phone": user_phone,
                "message": message,
                "groups": groups, 
                "interval_minutes": interval_minutes,
                "last_run": 0
            }
        )

    def get_user_schedules(self, user_phone: str) -> List[Dict]:
        try:
            result = self.databases.list_documents(
                DATABASE_ID,
                SCHEDULES_COLLECTION_ID,
                [self.Query.equal("user_phone", user_phone)]
            )
            return result['documents']
        except:
            return []

    def get_due_schedules(self) -> List[Dict]:
        try:
            result = self.databases.list_documents(DATABASE_ID, SCHEDULES_COLLECTION_ID)
            all_schedules = result['documents']
            
            now = time.time()
            due = []
            for schedule in all_schedules:
                last_run = schedule.get("last_run", 0)
                interval = schedule.get("interval_minutes", 10)
                if now - last_run >= interval * 60:
                    due.append(schedule)
            return due
        except Exception as e:
            print(f"Error fetching schedules: {e}")
            return []

    def update_last_run(self, schedule_id: str):
        self.databases.update_document(
            DATABASE_ID,
            SCHEDULES_COLLECTION_ID,
            schedule_id,
            {"last_run": int(time.time())}
        )

# Factory
if os.environ.get("APPWRITE_ENDPOINT"):
    db = AppwriteDatabase()
else:
    db = LocalDatabase()

# --- Main Function Logic ---

def get_json(context):
    try:
        return json.loads(context.req.body)
    except:
        return {}

def main(context):
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
        if path == '/cron' or path == '/':
            return asyncio.run(run_scheduler(context, headers))
        if path == '/auth/send_code' and method == 'POST':
            return asyncio.run(handle_send_code(context, headers))
        if path == '/auth/verify_code' and method == 'POST':
            return asyncio.run(handle_verify_code(context, headers))
        if path == '/groups' and method == 'POST':
            return asyncio.run(handle_get_groups(context, headers))
        if path == '/schedule' and method == 'POST':
            return handle_create_schedule(context, headers)
        if path == '/schedules' and method == 'POST':
            return handle_get_schedules(context, headers)
        if path == '/admin/users' and method == 'POST':
            return handle_admin_get_users(context, headers)
        if path == '/admin/user_status' and method == 'POST':
            return handle_admin_update_status(context, headers)
        if path == '/admin/stats' and method == 'POST':
            return handle_admin_stats(context, headers)

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
        
        db.update_last_run(schedule['$id'])

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

def handle_admin_get_users(context, headers):
    data = get_json(context)
    user_phone = data.get('user_phone')
    user = db.get_user(user_phone)
    if not user or user.get('role') != 'admin':
        return context.res.json({'error': 'Unauthorized'}, 403, headers)
    
    users = db.get_all_users()
    return context.res.json({'status': 'success', 'users': users}, 200, headers)

def handle_admin_update_status(context, headers):
    data = get_json(context)
    user_phone = data.get('user_phone')
    target_phone = data.get('target_phone')
    is_active = data.get('is_active')
    
    user = db.get_user(user_phone)
    if not user or user.get('role') != 'admin':
        return context.res.json({'error': 'Unauthorized'}, 403, headers)
        
    db.update_user_status(target_phone, is_active)
    return context.res.json({'status': 'success'}, 200, headers)

def handle_admin_stats(context, headers):
    data = get_json(context)
    user_phone = data.get('user_phone')
    user = db.get_user(user_phone)
    if not user or user.get('role') != 'admin':
        return context.res.json({'error': 'Unauthorized'}, 403, headers)
    
    users = db.get_all_users()
    return context.res.json({
        'status': 'success', 
        'stats': {
            'total_users': len(users),
            'active_users': len([u for u in users if u.get('is_active')])
        }
    }, 200, headers)
