from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from telegram_client import TelegramBot
from database import db
import os
import asyncio
from functools import wraps

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_demo'  # Change this!

# Global dictionary to hold temporary login states (Not serverless safe!)
# Key: phone_number, Value: { 'client': Client, 'phone_code_hash': str }
login_states = {}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_phone' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_phone' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user = db.get_user(session['user_phone'])
    schedules = db.get_user_schedules(session['user_phone'])
    return render_template('dashboard.html', user=user, schedules=schedules)

@app.route('/api/send_code', methods=['POST'])
async def send_code():
    data = request.json
    phone = data.get('phone')
    
    bot = TelegramBot()
    try:
        phone_code_hash = await bot.send_code(phone)
        # Store bot instance temporarily? No, can't pickle client easily.
        # We have to disconnect and reconnect.
        # But for verify_code we need the SAME connection or at least valid hash.
        # Pyrogram's send_code returns a hash that is valid for sign_in.
        # We don't need to keep the connection open if we have the hash.
        
        login_states[phone] = {'phone_code_hash': phone_code_hash}
        return jsonify({'status': 'success', 'message': 'Code sent'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/verify_code', methods=['POST'])
async def verify_code():
    data = request.json
    phone = data.get('phone')
    code = data.get('code')
    
    if phone not in login_states:
        return jsonify({'status': 'error', 'message': 'Request code first'}), 400
        
    phone_code_hash = login_states[phone]['phone_code_hash']
    bot = TelegramBot()
    
    try:
        session_string = await bot.verify_code(phone, phone_code_hash, code)
        db.save_user(phone, session_string)
        session['user_phone'] = phone
        del login_states[phone]
        return jsonify({'status': 'success', 'redirect': '/dashboard'})
    except Exception as e:
        if str(e) == "2FA_REQUIRED":
             return jsonify({'status': '2fa_required'}), 200
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/verify_password', methods=['POST'])
async def verify_password():
    # Implementing 2FA requires keeping the client state from verify_code step
    # which is hard in this stateless design without a persistent connection.
    # For this demo, we'll skip 2FA implementation or require disabling it.
    return jsonify({'status': 'error', 'message': '2FA not supported in this demo version. Please disable 2FA.'}), 400

@app.route('/api/groups', methods=['GET'])
@login_required
async def get_groups():
    user = db.get_user(session['user_phone'])
    bot = TelegramBot(user['session_string'])
    try:
        groups = await bot.get_groups()
        return jsonify({'status': 'success', 'groups': groups})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/schedule', methods=['POST'])
@login_required
def create_schedule():
    data = request.json
    message = data.get('message')
    groups = data.get('groups') # List of chat_ids
    interval = int(data.get('interval'))
    
    db.add_schedule(session['user_phone'], message, groups, interval)
    return jsonify({'status': 'success'})

@app.route('/admin')
@login_required
def admin():
    user = db.get_user(session['user_phone'])
    if user.get('role') != 'admin':
        return "Access Denied", 403
    
    users = db.get_all_users()
    return render_template('admin.html', users=users)

@app.route('/api/admin/user_status', methods=['POST'])
@login_required
def update_user_status():
    user = db.get_user(session['user_phone'])
    if user.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    target_phone = data.get('phone')
    is_active = data.get('is_active')
    
    # In a real DB, we would update the user. 
    # Our simple DB abstraction needs an update method.
    # For now, we'll just hack it by accessing the list directly via get_user (reference)
    # or adding a method to Database class.
    # Let's add a method to Database class first or just modify the dict if it's a reference.
    # get_user returns a reference to the dict in the list, so modifying it works if we save.
    
    target_user = db.get_user(target_phone)
    if target_user:
        target_user['is_active'] = is_active
        db._save() # Accessing protected method for brevity in this demo
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'User not found'}), 404

@app.route('/logout')
def logout():
    session.pop('user_phone', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
