import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
QUIZ_BOT_TOKEN = os.getenv('QUIZ_BOT_TOKEN', '6642298097:AAHXjwoFaTlP0Y7MuULbUoqHiUJOZO98v4k')
ANSWER_BOT_TOKEN = os.getenv('ANSWER_BOT_TOKEN', '6233735663:AAF6ULU2C0XAcyaKhXU6G7Bg39EXTVXWUwU')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '1352855793')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '1230R@j')

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'database.db')

# Flask Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# File Upload Configuration
UPLOAD_FOLDER = 'data'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'json'}

# Timezone Configuration
TIMEZONE = 'Asia/Kolkata'

# Quiz Configuration
DEFAULT_QUESTIONS_PER_QUIZ = 10
DEFAULT_POLL_DURATION = 300  # 5 minutes in seconds
QUIZ_INTERVAL_SECONDS = 10  # Interval between questions

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = 'logs/app.log'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Directory Configuration
DATA_DIR = 'data'
LOGS_DIR = 'logs'
STATIC_DIR = 'static'
TEMPLATES_DIR = 'templates'

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Categories
QUESTION_CATEGORIES = [
    'Mathematics',
    'Science',
    'History',
    'Geography',
    'General Knowledge',
    'English',
    'Hindi',
    'Computer Science',
    'Physics',
    'Chemistry',
    'Biology',
    'Economics',
    'Political Science',
    'Literature',
    'Current Affairs'
]

# Schedule intervals
SCHEDULE_INTERVALS = [
    'daily',
    'weekly',
    'monthly',
    'custom'
]

# Days of week
DAYS_OF_WEEK = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday'
]
    