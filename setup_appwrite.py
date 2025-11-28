from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException
import os
from dotenv import load_dotenv

load_dotenv()

APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT")
APPWRITE_PROJECT_ID = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("DATABASE_ID")
USERS_COLLECTION_ID = os.environ.get("USERS_COLLECTION_ID")
SCHEDULES_COLLECTION_ID = os.environ.get("SCHEDULES_COLLECTION_ID")

client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT_ID)
client.set_key(APPWRITE_API_KEY)

databases = Databases(client)

def setup():
    print("Setting up Appwrite Database...")
    
    # 1. Create Database
    try:
        databases.get(DATABASE_ID)
        print(f"Database '{DATABASE_ID}' already exists.")
    except AppwriteException as e:
        if e.code == 404:
            print(f"Creating database '{DATABASE_ID}'...")
            databases.create(DATABASE_ID, DATABASE_ID)
        else:
            print(f"Error checking database: {e}")
            return

    # 2. Create Users Collection
    try:
        databases.get_collection(DATABASE_ID, USERS_COLLECTION_ID)
        print(f"Collection '{USERS_COLLECTION_ID}' already exists.")
    except AppwriteException as e:
        if e.code == 404:
            print(f"Creating collection '{USERS_COLLECTION_ID}'...")
            databases.create_collection(DATABASE_ID, USERS_COLLECTION_ID, USERS_COLLECTION_ID)
            
            # Create Attributes
            print("Creating attributes for users...")
            databases.create_string_attribute(DATABASE_ID, USERS_COLLECTION_ID, "phone", 20, True)
            databases.create_string_attribute(DATABASE_ID, USERS_COLLECTION_ID, "session_string", 1000, True)
            databases.create_string_attribute(DATABASE_ID, USERS_COLLECTION_ID, "role", 20, False, "subscriber")
            databases.create_boolean_attribute(DATABASE_ID, USERS_COLLECTION_ID, "is_active", False, True)
        else:
            print(f"Error checking users collection: {e}")

    # 3. Create Schedules Collection
    try:
        databases.get_collection(DATABASE_ID, SCHEDULES_COLLECTION_ID)
        print(f"Collection '{SCHEDULES_COLLECTION_ID}' already exists.")
    except AppwriteException as e:
        if e.code == 404:
            print(f"Creating collection '{SCHEDULES_COLLECTION_ID}'...")
            databases.create_collection(DATABASE_ID, SCHEDULES_COLLECTION_ID, SCHEDULES_COLLECTION_ID)
            
            # Create Attributes
            print("Creating attributes for schedules...")
            databases.create_string_attribute(DATABASE_ID, SCHEDULES_COLLECTION_ID, "user_phone", 20, True)
            databases.create_string_attribute(DATABASE_ID, SCHEDULES_COLLECTION_ID, "message", 5000, True)
            # Storing groups as a list of integers is tricky in Appwrite if not using relationships.
            # We can use a string array or just a stringified JSON.
            # Appwrite supports Integer attributes, and array=True.
            databases.create_integer_attribute(DATABASE_ID, SCHEDULES_COLLECTION_ID, "groups", True) 
            databases.create_integer_attribute(DATABASE_ID, SCHEDULES_COLLECTION_ID, "interval_minutes", True)
            databases.create_integer_attribute(DATABASE_ID, SCHEDULES_COLLECTION_ID, "last_run", False, 0)
        else:
            print(f"Error checking schedules collection: {e}")

    print("Setup complete!")

if __name__ == "__main__":
    setup()
