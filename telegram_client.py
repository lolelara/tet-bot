import os
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid
from typing import List, Dict

# These should be loaded from environment variables in a real app
# For this demo, we will ask the user to input them or hardcode them if provided
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")

class TelegramBot:
    def __init__(self, session_string: str = None):
        self.session_string = session_string
        self.client = None

    async def connect(self):
        if not self.session_string:
            # For initial login, we use memory session
            self.client = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
        else:
            self.client = Client("user_session", session_string=self.session_string, api_id=API_ID, api_hash=API_HASH)
        
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
        try:
            await self.client.sign_in(phone_number, phone_code_hash, code)
            session_string = await self.client.export_session_string()
            await self.disconnect()
            return session_string
        except SessionPasswordNeeded:
            # 2FA is enabled
            await self.disconnect()
            raise Exception("2FA_REQUIRED")
        except Exception as e:
            await self.disconnect()
            raise e

    async def verify_password(self, password: str):
        # Re-connect needed? Usually sign_in throws error, client stays connected? 
        # Pyrogram flow: connect -> sign_in (error) -> check_password
        # Since we disconnected, we might need to handle this statefully in the app logic
        # For simplicity, we assume the client is still connected in the calling context if possible,
        # but here we are stateless between HTTP requests.
        # This is tricky for 2FA in a stateless REST API without keeping the client object alive.
        # We might need to cache the client object in a global dict for the duration of the login flow.
        pass 

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
