import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def load_questions_from_json(file_path: str) -> List[Dict[str, Any]]:
    """Load questions from JSON file"""
    try:
        if not os.path.exists(file_path):
            logger.warning(f"Questions file not found: {file_path}")
            return []
        
        with open(file_path, 'r', encoding='utf-8') as file:
            questions = json.load(file)
        
        logger.info(f"Loaded {len(questions)} questions from {file_path}")
        return questions
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {file_path}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error loading questions from {file_path}: {e}")
        return []

def save_questions_to_json(questions: List[Dict[str, Any]], file_path: str) -> bool:
    """Save questions to JSON file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(questions, file, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(questions)} questions to {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving questions to {file_path}: {e}")
        return False

def validate_question_format(questions: List[Dict[str, Any]]) -> bool:
    """Validate question format"""
    try:
        if not isinstance(questions, list):
            logger.error("Questions must be a list")
            return False
        
        required_fields = ['question', 'options', 'correct_answer', 'explanation']
        
        for i, question in enumerate(questions):
            if not isinstance(question, dict):
                logger.error(f"Question {i+1} must be a dictionary")
                return False
            
            # Check required fields
            for field in required_fields:
                if field not in question:
                    logger.error(f"Question {i+1} missing required field: {field}")
                    return False
            
            # Validate options
            if not isinstance(question['options'], list) or len(question['options']) != 4:
                logger.error(f"Question {i+1} must have exactly 4 options")
                return False
            
            # Validate correct answer
            if not isinstance(question['correct_answer'], int) or question['correct_answer'] not in range(4):
                logger.error(f"Question {i+1} correct_answer must be 0, 1, 2, or 3")
                return False
            
            # Validate question text
            if not isinstance(question['question'], str) or len(question['question'].strip()) == 0:
                logger.error(f"Question {i+1} must have valid question text")
                return False
            
            # Validate explanation
            if not isinstance(question['explanation'], str):
                logger.error(f"Question {i+1} explanation must be a string")
                return False
        
        logger.info(f"Validated {len(questions)} questions successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error validating questions: {e}")
        return False

def format_question_for_poll(question: Dict[str, Any]) -> Dict[str, Any]:
    """Format question for Telegram poll"""
    try:
        return {
            'question': question['question'],
            'options': question['options'],
            'correct_option_id': question['correct_answer'],
            'explanation': question['explanation']
        }
    except Exception as e:
        logger.error(f"Error formatting question for poll: {e}")
        return None

def create_sample_questions(category: str, count: int = 10) -> List[Dict[str, Any]]:
    """Create sample questions for testing"""
    samples = {
        'Mathematics': [
            {
                'question': 'What is 2 + 2?',
                'options': ['3', '4', '5', '6'],
                'correct_answer': 1,
                'explanation': '2 + 2 = 4',
                'reason': 'Basic addition: adding two and two gives four.'
            },
            {
                'question': 'What is the square root of 16?',
                'options': ['2', '3', '4', '5'],
                'correct_answer': 2,
                'explanation': '√16 = 4',
                'reason': '4 × 4 = 16, so the square root of 16 is 4.'
            }
        ],
        'Science': [
            {
                'question': 'What is the chemical symbol for water?',
                'options': ['H2O', 'CO2', 'O2', 'N2'],
                'correct_answer': 0,
                'explanation': 'Water is H2O',
                'reason': 'Water molecule consists of 2 hydrogen atoms and 1 oxygen atom.'
            },
            {
                'question': 'How many planets are in our solar system?',
                'options': ['7', '8', '9', '10'],
                'correct_answer': 1,
                'explanation': 'There are 8 planets in our solar system',
                'reason': 'Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, and Neptune.'
            }
        ],
        'History': [
            {
                'question': 'When did India gain independence?',
                'options': ['1945', '1947', '1948', '1950'],
                'correct_answer': 1,
                'explanation': 'India gained independence on August 15, 1947',
                'reason': 'India gained independence from British rule on August 15, 1947.'
            }
        ],
        'General Knowledge': [
            {
                'question': 'What is the capital of India?',
                'options': ['Mumbai', 'New Delhi', 'Kolkata', 'Chennai'],
                'correct_answer': 1,
                'explanation': 'New Delhi is the capital of India',
                'reason': 'New Delhi has been the capital of India since 1911.'
            }
        ]
    }
    
    base_questions = samples.get(category, samples['General Knowledge'])
    
    # Generate questions by repeating and modifying base questions
    questions = []
    for i in range(count):
        base_question = base_questions[i % len(base_questions)]
        question = base_question.copy()
        
        if i >= len(base_questions):
            question['question'] = f"Sample Question #{i+1}: {question['question']}"
        
        questions.append(question)
    
    return questions

def get_categories() -> List[str]:
    """Get available question categories"""
    return [
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
        'Political Science'
    ]

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations"""
    import re
    # Remove or replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    sanitized = sanitized.strip('. ')
    return sanitized

def calculate_quiz_duration(questions_count: int, seconds_per_question: int = 30) -> int:
    """Calculate total quiz duration in seconds"""
    return questions_count * seconds_per_question

def format_datetime_ist(dt: datetime.datetime) -> str:
    """Format datetime in IST timezone"""
    import pytz
    IST = pytz.timezone('Asia/Kolkata')
    
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    else:
        dt = dt.astimezone(IST)
    
    return dt.strftime('%Y-%m-%d %H:%M:%S IST')

def validate_channel_id(channel_id: str) -> bool:
    """Validate Telegram channel ID format"""
    import re
    
    # Check for @username format
    if channel_id.startswith('@'):
        return len(channel_id) > 1 and re.match(r'^@[a-zA-Z0-9_]+$', channel_id)
    
    # Check for numeric ID format
    try:
        numeric_id = int(channel_id)
        return numeric_id < 0  # Channel IDs are negative
    except ValueError:
        return False

def validate_discussion_group_id(group_id: str) -> bool:
    """Validate Telegram discussion group ID format"""
    # Same validation as channel ID
    return validate_channel_id(group_id)

def generate_quiz_report(channel_name: str, questions_sent: int, sent_at: datetime.datetime) -> str:
    """Generate quiz report text"""
    import datetime
    
    report = f"📊 **Quiz Report**\n\n"
    report += f"📺 **Channel:** {channel_name}\n"
    report += f"📝 **Questions Sent:** {questions_sent}\n"
    report += f"⏰ **Sent At:** {format_datetime_ist(sent_at)}\n"
    report += f"📅 **Date:** {sent_at.strftime('%A, %B %d, %Y')}\n\n"
    report += "✅ Quiz completed successfully!"
    
    return report
    