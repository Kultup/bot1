import telebot
from telebot import types
import re
import json
import sqlite3
import logging
import config
import requests

# Створюємо форматувальник для логування
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Створюємо об'єкт логгера
logger = logging.getLogger()
logger.setLevel(logging.ERROR)  # Встановлюємо рівень логування на ERROR

# Створюємо обробника файлу для логування помилок
file_handler = logging.FileHandler('bot_error_log.txt', encoding='utf-8')  
file_handler.setLevel(logging.ERROR)  
file_handler.setFormatter(formatter)

# Додаємо обробника до логгера
logger.addHandler(file_handler)

user_data = {}
request_counter = 0

languages = {
    'ukrainian': {
        'greet': "Вітаю! 😊",
        'choose_language': "Виберіть мову 🌐",
        'name_prompt': "Введіть ваше ім'я 📝",
        'phone_prompt': "Введіть ваш номер телефону 📱",
        'choose_currency': "Оберіть валюту 💵",
        'amount_prompt': "Введіть суму 💰",
        'purpose_prompt': "Введіть призначення платежу 📄",
        'thank_you': "Дякую за надану інформацію! 🙏",
        'invalid_phone': "Некоректний номер телефону. Будь ласка, введіть номер у форматі 0ХХXXXXXXXX",
        'invalid_amount': "Некоректна сума. Будь ласка, введіть числове значення суми.",
        'payment_approved': "Ваш платіж погоджено! ✅",
        'payment_rejected': "Ваш платіж відхилено! ❌",
        'exchange_rates': "Курси валют:\n{exchange_rates}",
    },
    'english': {
        'greet': "Hello! 😊",
        'choose_language': "Select your language: 🌐",
        'name_prompt': "Enter your name: 📝",
        'phone_prompt': "Enter your phone number: 📱",
        'choose_currency': "Choose currency: 💵",
        'amount_prompt': "Enter amount: 💰",
        'purpose_prompt': "Enter purpose of payment: 📄",
        'thank_you': "Thank you for the provided information! 🙏",
        'invalid_phone': "Invalid phone number. Please enter the phone number in the format 098XXXXXXXX",
        'invalid_amount': "Invalid amount. Please enter a numeric value for the amount.",
        'payment_approved': "Your payment has been approved! ✅",
        'payment_rejected': "Your payment has been rejected! ❌",
        'exchange_rates': "Exchange rates:\n{exchange_rates}",
    }
}

conn = sqlite3.connect('user_data.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        request_number INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        language TEXT,
        name TEXT,
        phone_number TEXT,
        currency TEXT,
        amount INTEGER,
        purpose TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()


def save_user_data(chat_id, language, name, phone_number, currency, amount, purpose):
    global request_counter
    request_counter += 1
    cursor.execute('''
        INSERT INTO users (request_number, chat_id, language, name, phone_number, currency, amount, purpose)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (request_counter, chat_id, language, name, phone_number, currency, amount, purpose))
    conn.commit()
    logging.info("User data saved successfully.")


def get_user_data(chat_id):
    cursor.execute('SELECT * FROM users WHERE chat_id=?', (chat_id,))
    return cursor.fetchone()


def update_currency_rates():
    try:
        response = requests.get("https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json")
        if response.status_code == 200:
            data = response.json()
            with open("currency_rates.json", "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            logging.info("Exchange rates updated successfully.")
            return True
        else:
            logging.error("Failed to fetch data from NBU API. Status code: %d", response.status_code)
    except Exception as e:
        logging.error("An error occurred while updating currency rates: %s", str(e))
    return False


chat_to_callback = {}


def get_purpose(message):
    user_data[message.chat.id]['purpose'] = message.text
    data = user_data[message.chat.id]
    bot.send_message(message.chat.id, languages[data['language']]['thank_you'])
    response = (
        f"Запит на погодження №{request_counter}\n"
        f"1. Ім'я: {data['name']}\n"
        f"2. Номер телефону: {data['phone_number']}\n"
        f"3. Валюта: {data['currency']}\n"
        f"4. Сума: {data['amount']}\n"
        f"5. Призначення платежу: {data['purpose']}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(text="Погодити", callback_data="approve"),
        types.InlineKeyboardButton(text="Відхилити", callback_data="reject")
    )
    bot.send_message(config.GROUP_ID, response, reply_markup=markup)
    chat_to_callback[config.GROUP_ID] = message.chat.id


@bot.message_handler(commands=['start'])
def start(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton(text="Українська 🇺🇦", callback_data='ukrainian'),
        types.InlineKeyboardButton(text="English 🇬🇧", callback_data='english')
    )
    bot.send_message(message.chat.id, languages['ukrainian']['greet'] + languages['ukrainian']['choose_language'],
                     reply_markup=keyboard)
    logging.info("Start command processed.")


@bot.callback_query_handler(func=lambda call: call.data in ['ukrainian', 'english'])
def language_callback_query(call):
    if call.data in ['ukrainian', 'english']:
        user_data[call.message.chat.id] = {'language': call.data}
        bot.send_message(call.message.chat.id, languages[call.data]['greet'] + languages[call.data]['name_prompt'])
        bot.register_next_step_handler(call.message, get_name)
        logging.info("Language selected: %s", call.data)


def get_name(message):
    user_data[message.chat.id]['name'] = message.text
    bot.send_message(message.chat.id, languages[user_data[message.chat.id]['language']]['phone_prompt'])
    bot.register_next_step_handler(message, get_phone_number)
    logging.info("Name received: %s", message.text)


def get_phone_number(message):
    phone_number = message.text
    if not re.match(r'^\d{10}$', phone_number):
        bot.send_message(message.chat.id, languages[user_data[message.chat.id]['language']]['invalid_phone'])
        bot.register_next_step_handler(message, get_phone_number)
        logging.warning("Invalid phone number format provided.")
        return
    user_data[message.chat.id]['phone_number'] = phone_number
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton(text="Гривні / UAH", callback_data='UAH'),
        types.InlineKeyboardButton(text="Долари / USD", callback_data='USD'),
        types.InlineKeyboardButton(text="Євро / EUR", callback_data='EUR')
    )
    bot.send_message(message.chat.id, languages[user_data[message.chat.id]['language']]['choose_currency'],
                     reply_markup=keyboard)
    logging.info("Phone number received: %s", phone_number)


@bot.callback_query_handler(func=lambda call: call.data in ['UAH', 'USD', 'EUR'])
def currency_callback_query(call):
    if call.data in ['UAH', 'USD', 'EUR']:
        user_data[call.message.chat.id]['currency'] = call.data
        bot.send_message(call.message.chat.id, languages[user_data[call.message.chat.id]['language']]['amount_prompt'])
        bot.register_next_step_handler(call.message, get_amount)
        logging.info("Currency selected: %s", call.data)


def get_amount(message):
    amount = message.text
    if not amount.isdigit():
        bot.send_message(message.chat.id, languages[user_data[message.chat.id]['language']]['invalid_amount'])
        bot.register_next_step_handler(message, get_amount)
        logging.warning("Invalid amount format provided.")
        return
    user_data[message.chat.id]['amount'] = amount
    bot.send_message(message.chat.id, languages[user_data[message.chat.id]['language']]['purpose_prompt'])
    bot.register_next_step_handler(message, get_purpose)
    logging.info("Amount received: %s", amount)


@bot.callback_query_handler(func=lambda call: call.data in ['approve', 'reject'])
def handle_approval(callback_query):
    chat_id = chat_to_callback.get(callback_query.message.chat.id)
    if chat_id is not None:
        if callback_query.data == 'approve':
            bot.send_message(chat_id, languages[user_data[chat_id]['language']]['payment_approved'])
            logging.info("Payment approved.")
        elif callback_query.data == 'reject':
            bot.send_message(chat_id, languages[user_data[chat_id]['language']]['payment_rejected'])
            logging.info("Payment rejected.")
    else:
        logging.error("Chat ID not found in chat_to_callback: %d", callback_query.message.chat.id)


@bot.message_handler(commands=['exchange'])
def exchange(message):
    if update_currency_rates():
        currency_rates = load_currency_rates()
        if currency_rates:
            exchange_rates_message = "\n".join(
                [f"{rate['cc']} - {rate['rate']}" for rate in currency_rates if rate['cc'] in ['USD', 'EUR', 'PLN']])
            bot.send_message(message.chat.id, "Курси валют:\n" + exchange_rates_message)
            logging.info("Exchange rates sent.")
        else:
            bot.send_message(message.chat.id, "Наразі обмінні курси недоступні.")
            logging.warning("Failed to load currency rates.")
    else:
        bot.send_message(message.chat.id, "Помилка при оновленні курсів валют. Спробуйте ще раз пізніше.")
        logging.error("Failed to update currency rates.")


def load_currency_rates():
    try:
        with open("currency_rates.json", "r", encoding="utf-8") as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        logging.error("Currency rates file not found.")
    except Exception as e:
        logging.error("An error occurred while loading currency rates from file: %s", str(e))
    return None


currency_rates = load_currency_rates()

bot.polling()
