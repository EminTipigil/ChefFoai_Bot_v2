import os
import json
import re
from dotenv import load_dotenv
from telebot import TeleBot, types
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise SystemExit("Set TELEGRAM_TOKEN and OPENAI_API_KEY in .env")

bot = TeleBot(TELEGRAM_TOKEN)
api_key = OPENAI_API_KEY
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
PREFS_FILE = os.path.join(DATA_DIR, "user_prefs.json")
SHOP_FILE = os.path.join(DATA_DIR, "shopping.json")
FAV_FILE = os.path.join(DATA_DIR, "favorites.json")


def load_json_file(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return default
    return default


LANG_RU = load_json_file("lang_ru.json", {})
LANG_EN = load_json_file("lang_en.json", {})


def get_user_pref(chat_id):
    prefs = load_json_file(PREFS_FILE, {})
    return prefs.get(str(chat_id), {"lang": "ru", "chef_mode": True})


def set_user_pref(chat_id, settings):
    prefs = load_json_file(PREFS_FILE, {})
    prefs[str(chat_id)] = settings
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


def t(chat_id, key):
    pref = get_user_pref(chat_id)
    lang = pref.get("lang", "ru")
    if lang == "en":
        return LANG_EN.get(key, key)
    return LANG_RU.get(key, key)


def append_history(chat_id, text):
    data = load_json_file(HISTORY_FILE, {})
    data.setdefault(str(chat_id), []).append(text)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_to_file(path, chat_id, item):
    data = load_json_file(path, {})
    lst = data.setdefault(str(chat_id), [])
    if item not in lst:
        lst.append(item)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def chef_say(chat_id, text):
    pref = get_user_pref(chat_id)
    chef_mode = pref.get("chef_mode", True)
    if chef_mode:
        if pref.get("lang", "ru") == "en":
            return "Oh la la! " + text
        else:
            return "Ммм, звучит аппетитно! " + text
    return text


@bot.message_handler(commands=['start'])
def cmd_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang:ru"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en")
    )
    bot.send_message(
        message.chat.id,
        "Выбери язык / Choose your language",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("set_lang:"))
def set_lang(call):
    lang = call.data.split(":", 1)[1]
    prefs = get_user_pref(call.message.chat.id)
    prefs["lang"] = lang
    prefs.setdefault("chef_mode", True)
    set_user_pref(call.message.chat.id, prefs)
    send_main_menu(call.message.chat.id)
    bot.answer_callback_query(call.id, "OK")


def main_menu_markup(chat_id):
    pref = get_user_pref(chat_id)
    lang = pref.get("lang", "ru")

    if lang == "en":
        labels = {
            "by_ingredients": "🥘 Recipe by ingredients",
            "random": "🎲 Random recipe",
            "diet": "🥗 Diet plan",
            "favorites": "❤️ Favorites",
            "tip": "🧠 Chef's tip",
            "settings": "⚙️ Settings"
        }
    else:
        labels = {
            "by_ingredients": "🥘 Рецепт по ингредиентам",
            "random": "🎲 Случайный рецепт",
            "diet": "🥗 Диетический план",
            "favorites": "❤️ Избранное",
            "tip": "🧠 Совет шефа",
            "settings": "⚙️ Настройки"
        }

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            labels["by_ingredients"], callback_data="menu:ingredients"),
        types.InlineKeyboardButton(
            labels["random"], callback_data="menu:random")
    )
    markup.add(
        types.InlineKeyboardButton(labels["diet"], callback_data="menu:diet"),
        types.InlineKeyboardButton(
            labels["favorites"], callback_data="menu:favorites")
    )
    markup.add(
        types.InlineKeyboardButton(labels["tip"], callback_data="menu:tip"),
        types.InlineKeyboardButton(
            labels["settings"], callback_data="menu:settings")
    )
    return markup


def send_main_menu(chat_id):
    bot.send_message(
        chat_id,
        chef_say(chat_id, t(chat_id, "main_menu")),
        reply_markup=main_menu_markup(chat_id)
    )


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("menu:"))
def menu_handler(call):
    action = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id

    if action == "ingredients":
        bot.send_message(chat_id, t(chat_id, "ask_ingredients"))

    elif action == "random":
        bot.send_message(
            chat_id,
            chef_say(chat_id, t(chat_id, "random_recipe") +
                     "\n\n" + "Паста с томатным соусом — 30 мин.")
        )

    elif action == "diet":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "Кето / Keto", callback_data="diet:keto"),
            types.InlineKeyboardButton(
                "Веган / Vegan", callback_data="diet:vegan")
        )
        bot.send_message(chat_id, "Выбери диету / Choose diet",
                         reply_markup=markup)

    elif action == "favorites":
        data = load_json_file(FAV_FILE, {}).get(str(chat_id), [])
        if not data:
            bot.send_message(chat_id, t(chat_id, "favorites_empty"))
        else:
            bot.send_message(chat_id, "\n\n".join(data[-10:]))

    elif action == "tip":
        bot.send_message(chat_id, chef_say(chat_id, t(chat_id, "chef_tip")))

    elif action == "settings":
        pref = get_user_pref(chat_id)
        cm_label = "Выкл. режим шефа" if pref.get(
            "chef_mode", True) else "Вкл. режим шефа"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            cm_label, callback_data="toggle:chefmode"))
        markup.add(types.InlineKeyboardButton(
            "Сменить язык / Change language", callback_data="change_lang"))
        bot.send_message(chat_id, "Настройки", reply_markup=markup)

    bot.answer_callback_query(call.id, "👍")


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("diet:"))
def diet_handler(call):
    diet = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    bot.send_message(chat_id, f"Готовлю план для: {diet}. (Пока это шаблон.)")
    bot.answer_callback_query(call.id, "Готово")


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("toggle:"))
def toggle_handler(call):
    key = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    prefs = get_user_pref(chat_id)
    if key == "chefmode":
        prefs["chef_mode"] = not prefs.get("chef_mode", True)
        set_user_pref(chat_id, prefs)
        bot.answer_callback_query(call.id, "Настройка обновлена")
        send_main_menu(chat_id)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("change_lang"))
def change_lang(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang:ru"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en")
    )
    bot.send_message(
        call.message.chat.id,
        "Выберите язык / Choose language",
        reply_markup=markup
    )
    bot.answer_callback_query(call.id, "OK")


@bot.message_handler(func=lambda m: True)
def catch_all(message):
    text = message.text.strip()
    if len(text.split()) > 0:
        prompt = (
            f"Ты — шеф-повар. Список продуктов: {text}. "
            "Предложи 2 простых рецепта на русском языке в формате: "
            "Название, Время, Ингредиенты, Рецепт (шаги)."
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system",
                        "content": "Ты — помощник-шеф, отвечай кратко и полезно."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=700,
                temperature=0.7
            )

            answer = resp.choices[0].message.content.strip()

        except Exception as e:
            answer = "Ошибка при запросе к OpenAI: " + str(e)

        append_history(message.chat.id, answer)

        if "🛒" in answer:
            part = answer.split("🛒", 1)[1]
            items = [
                re.sub(r'^[\-\•\s]+', '', ln).strip()
                for ln in part.splitlines()
                if ln.strip()
            ]
            for it in items:
                add_to_file(SHOP_FILE, message.chat.id, it)

        bot.send_message(message.chat.id, chef_say(message.chat.id, answer))
        send_main_menu(message.chat.id)

    else:
        bot.send_message(
            message.chat.id,
            "Не понимаю. Попробуй отправить список продуктов."
        )


if __name__ == "__main__":
    print("ChefFoai_Bot_v2 запускается...")
bot.infinity_polling()
