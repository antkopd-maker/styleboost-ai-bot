import os
import json
import openai
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

FREE_LIMIT = 5
MAX_TOKENS = 300
SUB_PRICE = 400  # цена подписки в сомах
DATA_FILE = "users.json"

openai.api_key = OPENAI_API_KEY

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ===== ЗАГРУЗКА ДАННЫХ =====
def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "users": {},
            "stats": {
                "total_users": 0,
                "total_generations": 0,
                "total_earnings": 0
            }
        }
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()
users = data["users"]
stats = data["stats"]

# ===== ПРОВЕРКА ДОСТУПА =====
def check_access(user_id):
    user_id_str = str(user_id)

    if user_id == ADMIN_ID:
        return True, "admin"

    if user_id_str in users and "expire" in users[user_id_str]:
        expire_date = datetime.strptime(users[user_id_str]["expire"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < expire_date:
            return True, "paid"

    if user_id_str not in users:
        users[user_id_str] = {"free_used": 0}
        stats["total_users"] += 1
        save_data(data)

    if users[user_id_str].get("free_used", 0) < FREE_LIMIT:
        return True, "free"

    return False, "none"

# ===== МЕНЮ =====
menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add("📸 Instagram", "💬 Telegram")
menu.add("🛍 Магазин")
menu.add("💎 Купить доступ")

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(
        "🚀 Добро пожаловать!\n\n"
        "5 бесплатных генераций.\n"
        "Подписка 400 сом / 30 дней.",
        reply_markup=menu
    )

# ===== ID =====
@dp.message_handler(commands=['id'])
async def get_id(message: types.Message):
    await message.answer(f"Твой ID: {message.from_user.id}")

# ===== СТАТИСТИКА (только админ) =====
@dp.message_handler(commands=['stats'])
async def show_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        f"📊 Статистика бота:\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"✍ Генераций всего: {stats['total_generations']}\n"
        f"💰 Заработано: {stats['total_earnings']} сом"
    )

# ===== GIVE (админ выдаёт доступ) =====
@dp.message_handler(commands=['give'])
async def give_access(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Используй: /give USER_ID [дни]")
        return

    user_id = parts[1]
    days = 30

    if len(parts) >= 3:
        days = int(parts[2])

    expire = datetime.now() + timedelta(days=days)

    users[user_id] = {
        "expire": expire.strftime("%Y-%m-%d %H:%M:%S"),
        "free_used": FREE_LIMIT
    }

    stats["total_earnings"] += SUB_PRICE
    save_data(data)

    await bot.send_message(user_id, f"🎉 Доступ активирован на {days} дней!")
    await message.answer("Готово ✅")

# ===== ПОКУПКА =====
@dp.message_handler(lambda m: m.text == "💎 Купить доступ")
async def buy(message: types.Message):
    await message.answer(
        "Оплати 400 сом.\n"
        "После оплаты отправь скрин.\n\n"
        f"Твой ID: {message.from_user.id}"
    )

# ===== ВЫБОР ПЛАТФОРМЫ =====
@dp.message_handler(lambda m: m.text in ["📸 Instagram", "💬 Telegram", "🛍 Магазин"])
async def choose_platform(message: types.Message):
    user_id = str(message.from_user.id)

    if user_id not in users:
        users[user_id] = {"free_used": 0}
        stats["total_users"] += 1

    users[user_id]["platform"] = message.text
    save_data(data)

    await message.answer("Теперь отправь фото 📸 или напиши тему")

# ===== ОБРАБОТКА ФОТО =====
@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    allowed, status = check_access(user_id)

    if not allowed:
        await message.answer("❌ Лимит исчерпан. Купи подписку.")
        return

    await message.answer("📸 Анализирую фото...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = file.file_path
    photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    platform = users.get(str(user_id), {}).get("platform", "Instagram")

    prompt = f"""
    Посмотри на фото.
    Сделай продающий текст для {platform}.
    Начни с 🔥
    В конце добавь хэштеги.
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": photo_url}},
                    ],
                }
            ],
            max_tokens=MAX_TOKENS,
        )

        result = response["choices"][0]["message"]["content"]
        await message.answer(result)

        stats["total_generations"] += 1

        if status == "free":
            users[str(user_id)]["free_used"] += 1

        save_data(data)

    except:
        await message.answer("Ошибка ИИ 😢")

# ===== ТЕКСТ =====
@dp.message_handler()
async def generate_text(message: types.Message):
    user_id = message.from_user.id
    allowed, status = check_access(user_id)

    if not allowed:
        await message.answer("❌ Лимит исчерпан. Купи подписку.")
        return

    platform = users.get(str(user_id), {}).get("platform", "Instagram")

    prompt = f"""
    Сделай продающий текст для {platform}.
    Тема: {message.text}
    Добавь хэштеги в конце.
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOKENS,
        )

        result = response["choices"][0]["message"]["content"]
        await message.answer(result)

        stats["total_generations"] += 1

        if status == "free":
            users[str(user_id)]["free_used"] += 1

        save_data(data)

    except:
        await message.answer("Ошибка ИИ 😢")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
