import sqlite3
import datetime
import pytz
from contextlib import contextmanager

IST = pytz.timezone('Asia/Kolkata')
DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        # Create channels table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT NOT NULL,
                channel_id TEXT NOT NULL UNIQUE,
                discussion_group_id TEXT,
                category TEXT NOT NULL,
                questions_per_batch INTEGER DEFAULT 10,
                active BOOLEAN DEFAULT 1,
                last_quiz_sent DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create questions table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option INTEGER NOT NULL,
                explanation TEXT,
                reason TEXT,
                used_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
        ''')
        
        # Create schedules table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                schedule_time TEXT NOT NULL,
                days_of_week TEXT NOT NULL,
                interval_type TEXT NOT NULL,
                active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
        ''')
        
        # Create quiz_history table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quiz_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                questions_sent INTEGER,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
        ''')
        
        conn.commit()

class Channel:
    def __init__(self, id=None, channel_name=None, channel_id=None, discussion_group_id=None, 
                 category=None, questions_per_batch=10, active=True):
        self.id = id
        self.channel_name = channel_name
        self.channel_id = channel_id
        self.discussion_group_id = discussion_group_id
        self.category = category
        self.questions_per_batch = questions_per_batch
        self.active = active
    
    def save(self):
        with get_db_connection() as conn:
            if self.id:
                # Update existing channel
                conn.execute('''
                    UPDATE channels 
                    SET channel_name=?, channel_id=?, discussion_group_id=?, 
                        category=?, questions_per_batch=?, active=?
                    WHERE id=?
                ''', (self.channel_name, self.channel_id, self.discussion_group_id,
                      self.category, self.questions_per_batch, self.active, self.id))
            else:
                # Insert new channel
                cursor = conn.execute('''
                    INSERT INTO channels (channel_name, channel_id, discussion_group_id, 
                                        category, questions_per_batch, active)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (self.channel_name, self.channel_id, self.discussion_group_id,
                      self.category, self.questions_per_batch, self.active))
                self.id = cursor.lastrowid
            conn.commit()
    
    @classmethod
    def get_all(cls):
        with get_db_connection() as conn:
            rows = conn.execute('SELECT * FROM channels ORDER BY channel_name').fetchall()
            return [cls(**dict(row)) for row in rows]
    
    @classmethod
    def get_by_id(cls, channel_id):
        with get_db_connection() as conn:
            row = conn.execute('SELECT * FROM channels WHERE id = ?', (channel_id,)).fetchone()
            return cls(**dict(row)) if row else None
    
    @classmethod
    def get_by_channel_id(cls, channel_id):
        with get_db_connection() as conn:
            row = conn.execute('SELECT * FROM channels WHERE channel_id = ?', (channel_id,)).fetchone()
            return cls(**dict(row)) if row else None

class Question:
    def __init__(self, id=None, channel_id=None, question_text=None, option_a=None, 
                 option_b=None, option_c=None, option_d=None, correct_option=None,
                 explanation=None, reason=None, used_count=0):
        self.id = id
        self.channel_id = channel_id
        self.question_text = question_text
        self.option_a = option_a
        self.option_b = option_b
        self.option_c = option_c
        self.option_d = option_d
        self.correct_option = correct_option
        self.explanation = explanation
        self.reason = reason
        self.used_count = used_count
    
    def save(self):
        with get_db_connection() as conn:
            if self.id:
                # Update existing question
                conn.execute('''
                    UPDATE questions 
                    SET question_text=?, option_a=?, option_b=?, option_c=?, option_d=?,
                        correct_option=?, explanation=?, reason=?, used_count=?
                    WHERE id=?
                ''', (self.question_text, self.option_a, self.option_b, self.option_c,
                      self.option_d, self.correct_option, self.explanation, self.reason,
                      self.used_count, self.id))
            else:
                # Insert new question
                cursor = conn.execute('''
                    INSERT INTO questions (channel_id, question_text, option_a, option_b, 
                                         option_c, option_d, correct_option, explanation, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (self.channel_id, self.question_text, self.option_a, self.option_b,
                      self.option_c, self.option_d, self.correct_option, self.explanation, self.reason))
                self.id = cursor.lastrowid
            conn.commit()
    
    @classmethod
    def get_by_channel(cls, channel_id, limit=None):
        with get_db_connection() as conn:
            if limit:
                rows = conn.execute('''
                    SELECT * FROM questions WHERE channel_id = ? 
                    ORDER BY used_count ASC, RANDOM() LIMIT ?
                ''', (channel_id, limit)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM questions WHERE channel_id = ? 
                    ORDER BY used_count ASC
                ''', (channel_id,)).fetchall()
            return [cls(**dict(row)) for row in rows]
    
    @classmethod
    def get_by_id(cls, question_id):
        with get_db_connection() as conn:
            row = conn.execute('SELECT * FROM questions WHERE id = ?', (question_id,)).fetchone()
            return cls(**dict(row)) if row else None

class Schedule:
    def __init__(self, id=None, channel_id=None, schedule_time=None, days_of_week=None,
                 interval_type=None, active=True):
        self.id = id
        self.channel_id = channel_id
        self.schedule_time = schedule_time
        self.days_of_week = days_of_week
        self.interval_type = interval_type
        self.active = active
    
    def save(self):
        with get_db_connection() as conn:
            if self.id:
                # Update existing schedule
                conn.execute('''
                    UPDATE schedules 
                    SET channel_id=?, schedule_time=?, days_of_week=?, 
                        interval_type=?, active=?
                    WHERE id=?
                ''', (self.channel_id, self.schedule_time, self.days_of_week,
                      self.interval_type, self.active, self.id))
            else:
                # Insert new schedule
                cursor = conn.execute('''
                    INSERT INTO schedules (channel_id, schedule_time, days_of_week, 
                                         interval_type, active)
                    VALUES (?, ?, ?, ?, ?)
                ''', (self.channel_id, self.schedule_time, self.days_of_week,
                      self.interval_type, self.active))
                self.id = cursor.lastrowid
            conn.commit()
    
    @classmethod
    def get_by_channel(cls, channel_id):
        with get_db_connection() as conn:
            rows = conn.execute('SELECT * FROM schedules WHERE channel_id = ?', (channel_id,)).fetchall()
            return [cls(**dict(row)) for row in rows]
    
    @classmethod
    def get_active_schedules(cls):
        with get_db_connection() as conn:
            rows = conn.execute('SELECT * FROM schedules WHERE active = 1').fetchall()
            return [cls(**dict(row)) for row in rows]
    