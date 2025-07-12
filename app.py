from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
import sqlite3
import json
import os
import logging
import datetime
import pytz
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import asyncio
import threading
from models import init_db, Channel, Question, Schedule, get_db_connection
from utils import load_questions_from_json, save_questions_to_json, validate_question_format
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this-in-production'
CORS(app)

# Configuration
ADMIN_PASSWORD = '1230R@j'
UPLOAD_FOLDER = 'data'
ALLOWED_EXTENSIONS = {'json'}
IST = pytz.timezone('Asia/Kolkata')

# Ensure required directories exist
os.makedirs('data', exist_ok=True)
os.makedirs('logs', exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Bot process management
bot_processes = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def requires_auth(f):
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@requires_auth
def dashboard():
    try:
        conn = get_db_connection()
        
        # Get statistics
        total_channels = conn.execute('SELECT COUNT(*) FROM channels').fetchone()[0]
        active_channels = conn.execute('SELECT COUNT(*) FROM channels WHERE active = 1').fetchone()[0]
        total_questions = conn.execute('SELECT COUNT(*) FROM questions').fetchone()[0]
        
        # Get recent activity
        recent_activity = conn.execute('''
            SELECT channel_name, last_quiz_sent, questions_per_batch 
            FROM channels 
            WHERE last_quiz_sent IS NOT NULL 
            ORDER BY last_quiz_sent DESC 
            LIMIT 10
        ''').fetchall()
        
        conn.close()
        
        stats = {
            'total_channels': total_channels,
            'active_channels': active_channels,
            'total_questions': total_questions,
            'recent_activity': recent_activity
        }
        
        return render_template('dashboard.html', stats=stats)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/channels')
@requires_auth
def channels():
    try:
        conn = get_db_connection()
        channels = conn.execute('SELECT * FROM channels ORDER BY channel_name').fetchall()
        conn.close()
        return render_template('channels.html', channels=channels)
    except Exception as e:
        logger.error(f"Channels error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels', methods=['GET'])
@requires_auth
def get_channels():
    try:
        conn = get_db_connection()
        channels = conn.execute('SELECT * FROM channels ORDER BY channel_name').fetchall()
        conn.close()
        
        channels_list = []
        for channel in channels:
            channels_list.append({
                'id': channel[0],
                'channel_name': channel[1],
                'channel_id': channel[2],
                'discussion_group_id': channel[3],
                'category': channel[4],
                'questions_per_batch': channel[5],
                'active': channel[6],
                'last_quiz_sent': channel[7],
                'created_at': channel[8]
            })
        
        return jsonify(channels_list)
    except Exception as e:
        logger.error(f"Get channels API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels', methods=['POST'])
@requires_auth
def add_channel():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['channel_name', 'channel_id', 'discussion_group_id', 'category']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        conn = get_db_connection()
        
        # Check if channel already exists
        existing = conn.execute('SELECT id FROM channels WHERE channel_id = ?', (data['channel_id'],)).fetchone()
        if existing:
            conn.close()
            return jsonify({'error': 'Channel already exists'}), 400
        
        # Insert new channel
        conn.execute('''
            INSERT INTO channels (channel_name, channel_id, discussion_group_id, category, questions_per_batch, active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['channel_name'],
            data['channel_id'],
            data['discussion_group_id'],
            data['category'],
            data.get('questions_per_batch', 10),
            data.get('active', True)
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Channel added successfully'}), 201
    except Exception as e:
        logger.error(f"Add channel API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels/', methods=['PUT'])
@requires_auth
def update_channel(channel_id):
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        
        # Check if channel exists
        existing = conn.execute('SELECT id FROM channels WHERE id = ?', (channel_id,)).fetchone()
        if not existing:
            conn.close()
            return jsonify({'error': 'Channel not found'}), 404
        
        # Update channel
        conn.execute('''
            UPDATE channels 
            SET channel_name = ?, channel_id = ?, discussion_group_id = ?, 
                category = ?, questions_per_batch = ?, active = ?
            WHERE id = ?
        ''', (
            data['channel_name'],
            data['channel_id'],
            data['discussion_group_id'],
            data['category'],
            data['questions_per_batch'],
            data['active'],
            channel_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Channel updated successfully'})
    except Exception as e:
        logger.error(f"Update channel API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels/', methods=['DELETE'])
@requires_auth
def delete_channel(channel_id):
    try:
        conn = get_db_connection()
        
        # Check if channel exists
        existing = conn.execute('SELECT id FROM channels WHERE id = ?', (channel_id,)).fetchone()
        if not existing:
            conn.close()
            return jsonify({'error': 'Channel not found'}), 404
        
        # Delete channel and related data
        conn.execute('DELETE FROM questions WHERE channel_id = ?', (channel_id,))
        conn.execute('DELETE FROM schedules WHERE channel_id = ?', (channel_id,))
        conn.execute('DELETE FROM channels WHERE id = ?', (channel_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Channel deleted successfully'})
    except Exception as e:
        logger.error(f"Delete channel API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-questions', methods=['POST'])
@requires_auth
def upload_questions():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        channel_id = request.form.get('channel_id')
        
        if not channel_id:
            return jsonify({'error': 'Channel ID is required'}), 400
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            try:
                # Read and validate JSON
                file_content = file.read().decode('utf-8')
                questions_data = json.loads(file_content)
                
                # Validate question format
                if not validate_question_format(questions_data):
                    return jsonify({'error': 'Invalid question format'}), 400
                
                # Save questions to database
                conn = get_db_connection()
                
                # Check if channel exists
                channel = conn.execute('SELECT id FROM channels WHERE id = ?', (channel_id,)).fetchone()
                if not channel:
                    conn.close()
                    return jsonify({'error': 'Channel not found'}), 404
                
                # Insert questions
                questions_added = 0
                for question in questions_data:
                    conn.execute('''
                        INSERT INTO questions (channel_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, reason)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        channel_id,
                        question['question'],
                        question['options'][0],
                        question['options'][1],
                        question['options'][2],
                        question['options'][3],
                        question['correct_answer'],
                        question['explanation'],
                        question.get('reason', '')
                    ))
                    questions_added += 1
                
                conn.commit()
                conn.close()
                
                return jsonify({'message': f'Successfully uploaded {questions_added} questions'}), 200
                
            except json.JSONDecodeError:
                return jsonify({'error': 'Invalid JSON format'}), 400
            except Exception as e:
                logger.error(f"Upload questions error: {e}")
                return jsonify({'error': str(e)}), 500
        else:
            return jsonify({'error': 'Invalid file type. Only JSON files are allowed'}), 400
    
    except Exception as e:
        logger.error(f"Upload questions API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/send-quiz', methods=['POST'])
@requires_auth
def send_quiz():
    try:
        data = request.get_json()
        channel_id = data.get('channel_id')
        
        if not channel_id:
            return jsonify({'error': 'Channel ID is required'}), 400
        
        # Get channel info
        conn = get_db_connection()
        channel = conn.execute('SELECT * FROM channels WHERE id = ?', (channel_id,)).fetchone()
        
        if not channel:
            conn.close()
            return jsonify({'error': 'Channel not found'}), 404
        
        # Get questions for this channel
        questions = conn.execute('''
            SELECT * FROM questions WHERE channel_id = ? ORDER BY RANDOM() LIMIT ?
        ''', (channel_id, channel[5])).fetchall()  # channel[5] is questions_per_batch
        
        conn.close()
        
        if not questions:
            return jsonify({'error': 'No questions available for this channel'}), 400
        
        # Here you would integrate with your quiz bot to send the quiz
        # For now, we'll simulate it
        logger.info(f"Sending quiz to channel {channel[2]} with {len(questions)} questions")
        
        return jsonify({'message': f'Quiz sent successfully to {channel[1]}'}), 200
        
    except Exception as e:
        logger.error(f"Send quiz API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot-control', methods=['POST'])
@requires_auth
def bot_control():
    try:
        data = request.get_json()
        action = data.get('action')
        bot_type = data.get('bot_type')  # 'quiz' or 'answer'
        
        if action == 'start':
            if bot_type == 'quiz':
                # Start quiz bot
                if 'quiz_bot' not in bot_processes:
                    process = subprocess.Popen([sys.executable, 'quiz_bot.py'])
                    bot_processes['quiz_bot'] = process
                    return jsonify({'message': 'Quiz bot started successfully'})
                else:
                    return jsonify({'message': 'Quiz bot is already running'})
            
            elif bot_type == 'answer':
                # Start answer bot
                if 'answer_bot' not in bot_processes:
                    process = subprocess.Popen([sys.executable, 'answer_bot.py'])
                    bot_processes['answer_bot'] = process
                    return jsonify({'message': 'Answer bot started successfully'})
                else:
                    return jsonify({'message': 'Answer bot is already running'})
        
        elif action == 'stop':
            if bot_type == 'quiz' and 'quiz_bot' in bot_processes:
                bot_processes['quiz_bot'].terminate()
                del bot_processes['quiz_bot']
                return jsonify({'message': 'Quiz bot stopped successfully'})
            
            elif bot_type == 'answer' and 'answer_bot' in bot_processes:
                bot_processes['answer_bot'].terminate()
                del bot_processes['answer_bot']
                return jsonify({'message': 'Answer bot stopped successfully'})
        
        elif action == 'status':
            status = {
                'quiz_bot': 'running' if 'quiz_bot' in bot_processes else 'stopped',
                'answer_bot': 'running' if 'answer_bot' in bot_processes else 'stopped'
            }
            return jsonify(status)
        
        return jsonify({'error': 'Invalid action or bot type'}), 400
        
    except Exception as e:
        logger.error(f"Bot control API error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
    