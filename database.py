import json
import os
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# Env vars for Appwrite
APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT")
APPWRITE_PROJECT_ID = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("DATABASE_ID", "telegram_bot_db")
USERS_COLLECTION_ID = os.environ.get("USERS_COLLECTION_ID", "users")
SCHEDULES_COLLECTION_ID = os.environ.get("SCHEDULES_COLLECTION_ID", "schedules")

class LocalDatabase:
    def __init__(self):
        # Use /tmp for Appwrite Function environment (read-only root)
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
            # user["role"] = role # Keep existing role
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
        # Appwrite stores arrays as list of strings usually, or relation. 
        # For simplicity assuming 'groups' is a string attribute (JSON) or array of integers if supported.
        # We'll store groups as a JSON string if needed, but Appwrite supports arrays.
        # Let's assume 'groups' attribute in Appwrite is an integer array.
        self.databases.create_document(
            DATABASE_ID,
            SCHEDULES_COLLECTION_ID,
            'unique()',
            {
                "user_phone": user_phone,
                "message": message,
                "groups": groups, # Ensure this attribute is array type in Appwrite
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
        # This logic is harder to do purely with queries if we need math (now - last_run >= interval).
        # We might need to fetch all active schedules and filter in python, 
        # or store 'next_run' timestamp in DB and query for next_run <= now.
        # For this implementation, let's fetch all and filter (not efficient for millions, ok for hundreds).
        try:
            result = self.databases.list_documents(DATABASE_ID, SCHEDULES_COLLECTION_ID)
            all_schedules = result['documents']
            
            now = time.time()
            due = []
            for schedule in all_schedules:
                # Appwrite returns attributes. Ensure types are correct.
                last_run = schedule.get("last_run", 0)
                interval = schedule.get("interval_minutes", 10)
                if now - last_run >= interval * 60:
                    due.append(schedule)
            return due
        except Exception as e:
            print(f"Error fetching schedules: {e}")
            return []

    def update_last_run(self, schedule_id: str):
        # schedule_id is the document $id
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
