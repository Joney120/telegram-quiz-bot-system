import asyncio
import json
import os
import logging
import datetime
import signal
import pytz
import sys
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, PollAnswerHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models import get_db_connection, Channel, Question, Schedule

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/quiz_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot configuration - Updated tokens
BOT_TOKEN = '6642298097:AAHXjwoFaTlP0Y7MuULbUoqHiUJOZO98v4k'
ADMIN_CHAT_ID = '1352855793'

# Set timezone for India
IST = pytz.timezone('Asia/Kolkata')

class QuizBot:
    def __init__(self):
        self.application = None
        self.scheduler = AsyncIOScheduler(timezone=IST)
        self.poll_storage = {}  # Store poll information for answer bot
        
    async def initialize(self):
        """Initialize the bot application"""
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("health", self.health_check))
        self.application.add_handler(CommandHandler("sendquiz", self.send_quiz_command))
        self.application.add_handler(CommandHandler("check_questions", self.check_questions))
        self.application.add_handler(CommandHandler("add_channel", self.add_channel_command))
        self.application.add_handler(CommandHandler("list_channels", self.list_channels))
        self.application.add_handler(CommandHandler("schedule_quiz", self.schedule_quiz_command))
        self.application.add_handler(PollAnswerHandler(self.handle_poll_answer))
        
        # Initialize and start scheduler
        self.scheduler.start()
        
        # Load existing schedules
        await self.load_schedules()
        
        logger.info("Quiz bot initialized successfully")
    
    async def load_schedules(self):
        """Load existing schedules from database"""
        try:
            schedules = Schedule.get_active_schedules()
            for schedule in schedules:
                await self.add_schedule_job(schedule)
            logger.info(f"Loaded {len(schedules)} active schedules")
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")
    
    async def add_schedule_job(self, schedule):
        """Add a scheduled job for a channel"""
        try:
            channel = Channel.get_by_id(schedule.channel_id)
            if not channel:
                logger.error(f"Channel not found for schedule {schedule.id}")
                return
            
            # Parse schedule time
            hour, minute = map(int, schedule.schedule_time.split(':'))
            
            # Parse days of week
            days = [int(d) for d in schedule.days_of_week.split(',')]
            
            # Add job to scheduler
            self.scheduler.add_job(
                func=self.send_scheduled_quiz,
                trigger='cron',
                day_of_week=','.join(map(str, days)),
                hour=hour,
                minute=minute,
                args=[channel.channel_id],
                id=f"quiz_{schedule.id}",
                replace_existing=True
            )
            
            logger.info(f"Added schedule job for channel {channel.channel_name}")
        except Exception as e:
            logger.error(f"Error adding schedule job: {e}")
    
    async def send_scheduled_quiz(self, channel_id):
        """Send scheduled quiz to a channel"""
        try:
            logger.info(f"Sending scheduled quiz to channel {channel_id}")
            await self.send_quiz_to_channel(channel_id)
        except Exception as e:
            logger.error(f"Error sending scheduled quiz: {e}")
    
    async def send_quiz_to_channel(self, channel_id):
        """Send quiz to a specific channel"""
        try:
            # Get channel information
            channel = Channel.get_by_channel_id(channel_id)
            if not channel:
                logger.error(f"Channel {channel_id} not found")
                return
            
            # Get questions for this channel
            questions = Question.get_by_channel(channel.id, limit=channel.questions_per_batch)
            
            if not questions:
                logger.warning(f"No questions available for channel {channel_id}")
                await self.application.bot.send_message(
                    chat_id=channel_id,
                    text="❌ No questions available for today's quiz."
                )
                return
            
            # Send start message
            await self.application.bot.send_message(
                chat_id=channel_id,
                text=f"🎓 **Quiz Time!** 📚\n\n"
                     f"Get ready for {len(questions)} questions!\n"
                     f"Category: {channel.category}\n\n"
                     f"Good luck! 🍀"
            )
            
            # Send each question as a poll
            for i, question in enumerate(questions, 1):
                try:
                    # Prepare options
                    options = [
                        question.option_a,
                        question.option_b,
                        question.option_c,
                        question.option_d
                    ]
                    
                    # Send poll
                    poll_message = await self.application.bot.send_poll(
                        chat_id=channel_id,
                        question=f"Q{i}: {question.question_text}",
                        options=options,
                        type="quiz",
                        correct_option_id=question.correct_option,
                        is_anonymous=False,
                        explanation=question.explanation or "Check discussion group for detailed explanation.",
                        open_period=300  # 5 minutes
                    )
                    
                    # Store poll information for answer bot
                    self.poll_storage[poll_message.poll.id] = {
                        'question': question,
                        'channel_id': channel_id,
                        'discussion_group_id': channel.discussion_group_id,
                        'poll_message': poll_message
                    }
                    
                    # Update question usage count
                    question.used_count += 1
                    question.save()
                    
                    logger.info(f"Sent poll Q{i} to {channel_id}")
                    
                    # Wait between questions
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    logger.error(f"Error sending poll Q{i}: {e}")
                    continue
            
            # Send completion message
            await self.application.bot.send_message(
                chat_id=channel_id,
                text="🎉 **Quiz Complete!** 🎉\n\n"
                     "Thank you for participating!\n"
                     "Detailed answers will be posted in the discussion group."
            )
            
            # Update channel last quiz sent
            with get_db_connection() as conn:
                conn.execute(
                    'UPDATE channels SET last_quiz_sent = ? WHERE id = ?',
                    (datetime.datetime.now(IST), channel.id)
                )
                conn.commit()
            
            logger.info(f"Quiz completed for channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Error sending quiz to channel {channel_id}: {e}")
    
    async def handle_poll_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle poll answers"""
        try:
            poll_answer = update.poll_answer
            user = poll_answer.user
            poll_id = poll_answer.poll_id
            
            # Log poll answer
            logger.info(f"User {user.username or user.first_name} answered poll {poll_id}")
            
        except Exception as e:
            logger.error(f"Error handling poll answer: {e}")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        try:
            await update.message.reply_text(
                '🤖 **Quiz Bot Active!** 🤖\n\n'
                'I can send automated quizzes to your channels.\n\n'
                '📋 **Available Commands:**\n'
                '• /sendquiz  - Send quiz now\n'
                '• /check_questions  - Check questions count\n'
                '• /add_channel - Add new channel\n'
                '• /list_channels - List all channels\n'
                '• /schedule_quiz - Schedule quiz\n'
                '• /health - Check bot status'
            )
        except Exception as e:
            logger.error(f"Error in start command: {e}")
    
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Health check command"""
        try:
            ist_time = datetime.datetime.now(IST)
            await update.message.reply_text(
                f'✅ **Bot Status: Healthy**\n\n'
                f'🕒 Current Time (IST): {ist_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                f'🔄 Scheduler Status: {"Running" if self.scheduler.running else "Stopped"}\n'
                f'📊 Active Jobs: {len(self.scheduler.get_jobs())}'
            )
        except Exception as e:
            logger.error(f"Error in health check: {e}")
    
    async def send_quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send quiz command handler"""
        try:
            if str(update.effective_chat.id) != ADMIN_CHAT_ID:
                await update.message.reply_text("❌ Admin only command!")
                return
            
            if not context.args:
                await update.message.reply_text(
                    "📝 **Usage:** /sendquiz \n\n"
                    "Example: /sendquiz @mychannel"
                )
                return
            
            channel_id = context.args[0]
            
            await update.message.reply_text(f"🚀 Starting quiz for {channel_id}...")
            await self.send_quiz_to_channel(channel_id)
            
        except Exception as e:
            logger.error(f"Error in send quiz command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def check_questions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check questions command handler"""
        try:
            if str(update.effective_chat.id) != ADMIN_CHAT_ID:
                await update.message.reply_text("❌ Admin only command!")
                return
            
            if not context.args:
                await update.message.reply_text(
                    "📝 **Usage:** /check_questions \n\n"
                    "Example: /check_questions @mychannel"
                )
                return
            
            channel_id = context.args[0]
            channel = Channel.get_by_channel_id(channel_id)
            
            if not channel:
                await update.message.reply_text(f"❌ Channel {channel_id} not found!")
                return
            
            questions = Question.get_by_channel(channel.id)
            
            await update.message.reply_text(
                f"📊 **Channel: {channel.channel_name}**\n\n"
                f"📝 Total Questions: {len(questions)}\n"
                f"🎯 Questions per Quiz: {channel.questions_per_batch}\n"
                f"📅 Last Quiz: {channel.last_quiz_sent or 'Never'}\n"
                f"🏷️ Category: {channel.category}"
            )
            
        except Exception as e:
            logger.error(f"Error in check questions: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def add_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add channel command handler"""
        try:
            if str(update.effective_chat.id) != ADMIN_CHAT_ID:
                await update.message.reply_text("❌ Admin only command!")
                return
            
            await update.message.reply_text(
                "📝 **Add Channel via Web Panel**\n\n"
                "Please use the web administration panel to add new channels.\n"
                "This provides a better interface for channel management."
            )
            
        except Exception as e:
            logger.error(f"Error in add channel command: {e}")
    
    async def list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List channels command handler"""
        try:
            if str(update.effective_chat.id) != ADMIN_CHAT_ID:
                await update.message.reply_text("❌ Admin only command!")
                return
            
            channels = Channel.get_all()
            
            if not channels:
                await update.message.reply_text("📋 No channels configured yet.")
                return
            
            message = "📋 **Configured Channels:**\n\n"
            for channel in channels:
                status = "✅ Active" if channel.active else "❌ Inactive"
                message += f"• **{channel.channel_name}**\n"
                message += f"  ID: {channel.channel_id}\n"
                message += f"  Category: {channel.category}\n"
                message += f"  Status: {status}\n\n"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error in list channels: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def schedule_quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Schedule quiz command handler"""
        try:
            if str(update.effective_chat.id) != ADMIN_CHAT_ID:
                await update.message.reply_text("❌ Admin only command!")
                return
            
            await update.message.reply_text(
                "⏰ **Schedule Quiz via Web Panel**\n\n"
                "Please use the web administration panel to schedule quizzes.\n"
                "This provides a better interface for scheduling management."
            )
            
        except Exception as e:
            logger.error(f"Error in schedule quiz command: {e}")
    
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
            
            logger.info("Quiz bot started successfully!")
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error running quiz bot: {e}")
        finally:
            # Cleanup
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            if self.scheduler.running:
                self.scheduler.shutdown()

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    logger.info("Received signal to terminate quiz bot.")
    raise KeyboardInterrupt

async def main():
    """Main function"""
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Create and run bot
        bot = QuizBot()
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("Quiz bot stopping...")
    except Exception as e:
        logger.error(f"Fatal error in quiz bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    