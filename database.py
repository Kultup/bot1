import sqlite3

conn = sqlite3.connect('user_data.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        chat_id INTEGER,
        language TEXT,
        name TEXT,
        phone_number TEXT,
        currency TEXT,
        amount INTEGER,
        purpose TEXT
    )
''')
conn.commit()

def save_user_data(chat_id, language, name, phone_number, currency, amount, purpose):
    cursor.execute('''
        INSERT INTO users (chat_id, language, name, phone_number, currency, amount, purpose)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (chat_id, language, name, phone_number, currency, amount, purpose))
    conn.commit()

def get_user_data(chat_id):
    cursor.execute('SELECT * FROM users WHERE chat_id=?', (chat_id,))
    return cursor.fetchone()

def update_user_data(chat_id, language, name, phone_number, currency, amount, purpose):
    cursor.execute('''
        UPDATE users
        SET language=?, name=?, phone_number=?, currency=?, amount=?, purpose=?
        WHERE chat_id=?
    ''', (language, name, phone_number, currency, amount, purpose, chat_id))
    conn.commit()
