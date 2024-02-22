from telebot import types
from dotenv import load_dotenv
import telebot
import requests
import re
import threading
import time
import os

load_dotenv('.env')

chat_id = os.getenv('CHAT_ID')
bot_token = os.getenv('BOT_TOKEN')
chat_id = '5612869186'
bot = telebot.TeleBot('bot_token')
TARGET_PRICES = {}
MONITORED_SKINS = set()


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == 'help':
        help(call.message)


@bot.message_handler(commands=['start'])
def start(message):
    start_message = """
    "Привет! Для получения информации введите /help"
    """
    markup = types.InlineKeyboardMarkup()
    help_button = types.InlineKeyboardButton("Помощь", callback_data='help')
    markup.add(help_button)
    bot.send_message(message.chat.id, start_message, reply_markup=markup)


@bot.message_handler(commands=['check_price'])
def check_price(message):
    try:
        item_url = message.text.split(' ', 1)[1]
        item_name = extract_item_name_from_url(item_url)

        if item_name:
            price = get_steam_skin_price(item_name)

            if price:
                bot.send_message(message.chat.id, f'Текущая цена для {item_name}: {price}')
            else:
                bot.send_message(message.chat.id, f'Ошибка: Не удалось получить цену для {item_name}')
        else:
            bot.send_message(message.chat.id, 'Ошибка: Не удалось извлечь название скина из URL. Убедитесь, что ссылка ведет на мастерскую Steam.')

    except:
        bot.send_message(message.chat.id, 'Ошибка при проверке цены скина. Пожалуйста, используйте формат: /check_price <URL скина>')


def extract_item_name_from_url(url):
    pattern = r'https://steamcommunity.com/market/listings/\d+/(.*)'
    match = re.match(pattern, url)

    if match:
        item_name = match.group(1).replace('%20', ' ').replace('%7C', '|')
        return item_name
    else:
        return None


@bot.message_handler(commands=['track_item'])
def track_item(message):
    try:
        item_info = message.text.split(' ', 1)[1].split(',')
        item_url = item_info[0].strip()
        target_price = float(item_info[1].strip().replace(',', '.'))

        item_name = extract_item_name_from_url(item_url)

        if item_name:
            price = get_steam_skin_price(item_name)

            if price:
                bot.send_message(message.chat.id, f'Вы начали мониторинг цены для скина: {item_name} с желаемой ценой {target_price}')
                MONITORED_SKINS.add((item_name, target_price))
            else:
                bot.send_message(message.chat.id, f'Ошибка: Не удалось получить цену для скина {item_name}')
        else:
            bot.send_message(message.chat.id, 'Ошибка при извлечении названия скина из URL. Убедитесь, что ссылка ведет на мастерскую Steam.')

    except:
        bot.send_message(message.chat.id, 'Ошибка при добавлении скина. Пожалуйста, используйте формат: /track_item <URL скина>, <желаемая цена>')


@bot.message_handler(commands=['stop_tracking'])
def stop_tracking(message):
    try:
        skin_number = int(message.text.split(' ', 1)[1])
        if skin_number <= len(MONITORED_SKINS):
            skin_to_remove = list(MONITORED_SKINS)[skin_number - 1]
            MONITORED_SKINS.remove(skin_to_remove)
            bot.send_message(message.chat.id, f'Мониторинг для скина {skin_to_remove} (номер {skin_number}) остановлен')
        else:
            bot.send_message(message.chat.id, f'Ошибка: Некорректный номер скина')
    except:
        bot.send_message(message.chat.id, 'Ошибка при остановке мониторинга. Пожалуйста, используйте формат: /stop_tracking <номер скина>')


@bot.message_handler(commands=['monitored_skins'])
def monitored_skins(message):
    response = 'Сейчас мониторятся следующие скины:\n'

    if not MONITORED_SKINS:
        bot.send_message(message.chat.id, "Нет скинов на мониторинге.")
    else:
        try:
            for idx, item_info in enumerate(MONITORED_SKINS, 1):
                item_name = item_info[0]
                target_price = item_info[1]
                current_price = get_steam_skin_price(item_name)

                if current_price:
                    response += f'{idx}. {item_name}: Желаемая цена - {target_price}, Текущая цена - {current_price}\n'
                else:
                    response += f'{idx}. {item_name}: Цена не доступна\n'
            bot.send_message(message.chat.id, response)
        except:
            bot.send_message(message.chat.id, "Ошибка при получении цен скинов.")


@bot.message_handler(commands=['help'])
def help(message):
    commands_info = """
    Список доступных команд:
    /start - Начать работу.
    /stop_tracking <номер скина> - Остановить мониторинг скина.
    /monitored_skins - Показать список мониторируемых скинов.
    /help - Показать это сообщение с описанием команд.
    /check_price <url скина> - Показать текущую цену скина.
    """
    bot.send_message(message.chat.id, commands_info)
    bot.send_message(message.chat.id, """/track_item <url скина> <желаемая цена> - Начать мониторинг цены для указанного скина.""")


def check_steam_skin_price(item_name, target_price, chat_id):
    current_price = get_steam_skin_price(item_name)
    if current_price and float(current_price.replace(',', '').replace('.', '')) >= target_price:
        message = f'Цена скина {item_name} достигла {target_price}!'
        bot.send_message(chat_id, message)


def get_steam_skin_price(item_name):
    url = f'http://steamcommunity.com/market/priceoverview/?appid=730&market_hash_name={item_name}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data.get('success') and 'lowest_price' in data:
            lowest_price = data.get('lowest_price')
            return lowest_price
    return False


def check_prices_periodically(chat_id):
    print("Проверка цен скинов начата...")

    while True:
        for item_name, target_price in MONITORED_SKINS:
            current_price = get_steam_skin_price(item_name)
            if current_price:
                current_price_cleaned = current_price.replace(',', '').replace('.', '')
                
                try:
                    current_price_float = float(re.sub(r'[^\d.]', '', current_price_cleaned))
                    target_price_float = float(target_price)
                    
                    if current_price_float >= target_price_float:
                        message_text = f'Цена скина {item_name} достигла или превысила {target_price}! Текущая цена: {current_price}'
                        bot.send_message(chat_id, message_text)
                except ValueError:
                    print(f'Ошибка при сравнении цен для скина {item_name}')
                    bot.send_message(chat_id, f'Ошибка: Невозможно сравнить цены для скина {item_name}')

            else:
                print(f'Ошибка при получении цены для скина {item_name}')
                bot.send_message(chat_id, f'Ошибка: Невозможно получить цену для скина {item_name}')

        time.sleep(60)  # Подождать 60 секунд (1 минуту) перед следующей проверкой


if __name__ == '__main__':
    threading.Thread(target=check_prices_periodically, args=(chat_id,)).start()
    bot.polling()