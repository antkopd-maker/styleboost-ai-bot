import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup
from openai import OpenAI

# ===== НАСТРОЙКИ =====
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 650700815

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

DATA_FILE = "users.json"

# ===== ЗАГРУЗКА =====
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

users = load_data()

# ===== ДОСТУП =====
def has_access(user_id):
    user_id = str(user_id)
    if user_id in users:
        expire = users[user_id].get("expire")
        if expire:
            expire_date = datetime.strptime(expire, "%Y-%m-%d %H:%M:%S")
            return datetime.now() < expire_date
    return False

# ===== МЕНЮ =====
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🚀 Создать текст")
    kb.add("💎 Купить доступ", "📅 Мой доступ")
    kb.add("ℹ Что умеет бот")
    return kb

def format_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📸 Instagram", "💬 Telegram")
    kb.add("🛍 Магазин")
    kb.add("⬅ Главное меню")
    return kb

user_mode = {}

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(
        "🔥 StyleBoost AI\n\nAI-ассистент для продавцов одежды.",
        reply_markup=main_menu()
    )

# ===== СОЗДАТЬ ТЕКСТ =====
@dp.message_handler(lambda m: m.text == "🚀 Создать текст")
async def create_text(message: types.Message):
    await message.answer("Выберите площадку 👇", reply_markup=format_menu())

# ===== ВЫБОР ФОРМАТА =====
@dp.message_handler(lambda m: m.text in ["📸 Instagram", "💬 Telegram", "🛍 Магазин"])
async def choose_format(message: types.Message):
    if not has_access(message.from_user.id):
        await message.answer("❌ Нет доступа.", reply_markup=main_menu())
        return

    user_mode[message.from_user.id] = message.text
    await message.answer("📷 Отправьте фото или напишите описание товара.")

# ===== AI =====
@dp.message_handler(content_types=['text', 'photo'])
async def ai_generate(message: types.Message):
    user_id = message.from_user.id

    if user_id not in user_mode:
        return

    mode = user_mode[user_id]

    if message.photo:
        file = await bot.get_file(message.photo[-1].file_id)
        photo_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
        user_content = [
            {"type": "text", "text": "Опиши товар и сделай продающий текст."},
            {"type": "image_url", "image_url": {"url": photo_url}}
        ]
    else:
        user_content = message.text

    if mode == "📸 Instagram":
        system_text = "Ты маркетолог Instagram. Яркий текст с эмодзи и хештегами."
    elif mode == "💬 Telegram":
        system_text = "Ты маркетолог Telegram. Коротко, без хештегов."
    else:
        system_text = "Структурированное описание для интернет-магазина."

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_content}
        ],
        max_tokens=300
    )

    ai_text = response.choices[0].message.content

    await message.answer(ai_text, reply_markup=main_menu())
    del user_mode[user_id]

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
