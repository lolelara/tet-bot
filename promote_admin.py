from database import db
import sys

def promote(phone):
    print(f"Promoting user {phone} to admin...")
    user = db.get_user(phone)
    if not user:
        print("User not found! Please login with this number first.")
        return

    # Assuming db abstraction has a way to update role, or we use Appwrite directly here
    # Since database.py is designed for Appwrite, let's see if it has update_role
    # It doesn't have explicit update_role, but we can use the underlying client if needed
    # Or just update the document directly using Appwrite SDK here.
    
    if hasattr(db, 'databases'):
        try:
            db.databases.update_document(
                db.DATABASE_ID, # Accessing class attributes might need adjustment if they are not exposed
                # Wait, DATABASE_ID is global in database.py, not in class instance usually unless assigned
                # Let's check database.py structure again.
                # It uses global vars for ID.
                # We can import them.
                "tele-bot", # Hardcoded from previous context or imported
                "users",
                user['$id'],
                {"role": "admin"}
            )
            print("Success! User is now Admin.")
        except Exception as e:
            print(f"Error: {e}")
            # Fallback for local db
            if hasattr(db, 'data'):
                 user['role'] = 'admin'
                 db._save()
                 print("Success (Local DB)!")

if __name__ == "__main__":
    target_phone = "+201550504273"
    promote(target_phone)
