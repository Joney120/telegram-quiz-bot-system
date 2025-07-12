import asyncio
import json
import logging
import datetime
import signal
import pytz
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from models import get_db_connection, Channel, Question

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/answer_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot configuration - Updated tokens
BOT_TOKEN = '6233735663:AAF6ULU2C0XAcyaKhXU6G7Bg39EXTVXWUwU'
ADMIN_CHAT_ID = '1352855793'

# Set timezone for India
IST = pytz.timezone('Asia/Kolkata')

class AnswerBot:
    def __init__(self):
        self.application = None
        self.question_database = {}  # Store questions for lookup
        
    async def initialize(self):
        """Initialize the bot application"""
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("health", self.health_check))
        self.application.add_handler(CommandHandler("reload_questions", self.reload_questions))
        self.application.add_handler(MessageHandler(filters.POLL, self.handle_poll))
        
        # Load questions database
        await self.load_questions_database()
        
        logger.info("Answer bot initialized successfully")
    
    async def load_questions_database(self):
        """Load all questions into memory for fast lookup"""
        try:
            with get_db_connection() as conn:
                questions = conn.execute('''
                    SELECT q.*, c.channel_id, c.discussion_group_id, c.channel_name
                    FROM questions q
                    JOIN channels c ON q.channel_id = c.id
                    WHERE c.active = 1
                ''').fetchall()
                
                for question in questions:
                    # Create a searchable key from question text
                    question_key = self.normalize_question_text(question[2])  # question_text
                    
                    self.question_database[question_key] = {
                        'id': question[0],
                        'channel_id': question[1],
                        'question_text': question[2],
                        'option_a': question[3],
                        'option_b': question[4],
                        'option_c': question[5],
                        'option_d': question[6],
                        'correct_option': question[7],
                        'explanation': question[8],
                        'reason': question[9],
                        'channel_telegram_id': question[11],
                        'discussion_group_id': question[12],
                        'channel_name': question[13]
                    }
                
                logger.info(f"Loaded {len(self.question_database)} questions into memory")
        except Exception as e:
            logger.error(f"Error loading questions database: {e}")
    
    def normalize_question_text(self, text):
        """Normalize question text for matching"""
        # Remove extra whitespace, convert to lowercase, remove special characters
        import re
        normalized = re.sub(r'[^\w\s]', '', text.lower().strip())
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    async def handle_poll(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming polls and provide answers"""
        try:
            message = update.effective_message
            poll = message.poll
            
            if not poll:
                return
            
            # Extract question text from poll
            poll_question = poll.question
            
            # Remove question number prefix if present (e.g., "Q1: ")
            import re
            clean_question = re.sub(r'^Q\d+:\s*', '', poll_question)
            
            # Normalize for search
            normalized_question = self.normalize_question_text(clean_question)
            
            # Search for matching question
            matching_question = None
            for question_key, question_data in self.question_database.items():
                if question_key in normalized_question or normalized_question in question_key:
                    matching_question = question_data
                    break
            
            if not matching_question:
                logger.info(f"No matching question found for: {clean_question}")
                return
            
            # Get discussion group ID
            discussion_group_id = matching_question['discussion_group_id']
            if not discussion_group_id:
                logger.warning(f"No discussion group configured for question: {clean_question}")
                return
            
            # Wait for poll to close (or timeout)
            await asyncio.sleep(320)  # Wait 5 minutes + 20 seconds buffer
            
            # Prepare answer message
            options = [
                matching_question['option_a'],
                matching_question['option_b'],
                matching_question['option_c'],
                matching_question['option_d']
            ]
            
            correct_option_index = matching_question['correct_option']
            correct_answer = options[correct_option_index]
            
            # Format answer message
            answer_message = f"📝 **Answer Explanation**\n\n"
            answer_message += f"❓ **Question:** {matching_question['question_text']}\n\n"
            answer_message += f"✅ **Correct Answer:** {chr(65 + correct_option_index)} - {correct_answer}\n\n"
            
            if matching_question['explanation']:
                answer_message += f"💡 **Explanation:** {matching_question['explanation']}\n\n"
            
            if matching_question['reason']:
                answer_message += f"🔍 **Detailed Reason:** {matching_question['reason']}\n\n"
            
            answer_message += f"📚 **Channel:** {matching_question['channel_name']}\n"
            answer_message += f"⏰ **Answered at:** {datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}"
            
            # Send answer to discussion group
            await self.application.bot.send_message(
                chat_id=discussion_group_id,
                text=answer_message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Sent answer explanation to discussion group for question: {clean_question}")
            
        except Exception as e:
            logger.error(f"Error handling poll: {e}")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        try:
            await update.message.reply_text(
                '🤖 **Answer Bot Active!** 🤖\n\n'
                'I automatically provide detailed answers to quiz questions!\n\n'
                '📋 **What I Do:**\n'
                '• Monitor quiz polls in channels\n'
                '• Wait for polls to close\n'
                '• Post detailed answers in discussion groups\n'
                '• Provide explanations and reasoning\n\n'
                '📊 **Commands:**\n'
                '• /health - Check bot status\n'
                '• /reload_questions - Reload question database'
            )
        except Exception as e:
            logger.error(f"Error in start command: {e}")
    
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Health check command"""
        try:
            ist_time = datetime.datetime.now(IST)
            await update.message.reply_text(
                f'✅ **Answer Bot Status: Healthy**\n\n'
                f'🕒 Current Time (IST): {ist_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                f'📊 Questions in Database: {len(self.question_database)}\n'
                f'🔍 Monitoring: Poll messages'
            )
        except Exception as e:
            logger.error(f"Error in health check: {e}")
    
    async def reload_questions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reload questions database"""
        try:
            if str(update.effective_chat.id) != ADMIN_CHAT_ID:
                await update.message.reply_text("❌ Admin only command!")
                return
            
            await update.message.reply_text("🔄 Reloading questions database...")
            await self.load_questions_database()
            
            await update.message.reply_text(
                f"✅ **Questions Database Reloaded!**\n\n"
                f"📊 Total Questions: {len(self.question_database)}"
            )
            
        except Exception as e:
            logger.error(f"Error reloading questions: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def run(self):
        """Run the bot"""
        try:
            await self.initialize()
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES
            )
            
            logger.info("Answer bot started successfully!")
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error running answer bot: {e}")
        finally:
            # Cleanup
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    logger.info("Received signal to terminate answer bot.")
    raise KeyboardInterrupt

async def main():
    """Main function"""
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Create and run bot
        bot = AnswerBot()
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("Answer bot stopping...")
    except Exception as e:
        logger.error(f"Fatal error in answer bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    