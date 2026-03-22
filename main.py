from asyncio import run, sleep
from aiogram import types, Bot, Dispatcher
from aiogram.filters import ChatMemberUpdatedFilter
from aiogram.filters.chat_member_updated import IS_NOT_MEMBER, IS_MEMBER, ADMINISTRATOR, CREATOR
from aiogram.filters.command import Command
from os import getenv
from dotenv import load_dotenv
import time

load_dotenv()

import aiohttp
import json

CALLS_BASE_URL = getenv("CALLS_BASE_URL")
CALLS_API_KEY = getenv("CALLS_API_KEY")

with open("db.json") as f:
    db = json.load(f)

try:
    with open("bans_log.json") as f:
        bans_log = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    bans_log = []

# chat_id (str) -> list of user_ids
try:
    with open("members.json") as f:
        chat_members: dict[str, list[int]] = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    chat_members = {}


def track_member(chat_id: int, user_id: int):
    key = str(chat_id)
    if key not in chat_members:
        chat_members[key] = []
    if user_id not in chat_members[key]:
        chat_members[key].append(user_id)
        with open("members.json", "w") as f:
            json.dump(chat_members, f)


def get_daily_count() -> int:
    now = time.time()
    return sum(1 for entry in bans_log if now - entry["ts"] < 86400)


def save_ban_log(user_id: int):
    bans_log.append({"id": user_id, "ts": time.time()})
    with open("bans_log.json", "w") as f:
        json.dump(bans_log, f)


async def is_telega_user(telegram_id: int) -> bool:
    if telegram_id in db:
        return True
    async with aiohttp.ClientSession() as session:
        auth_payload = {
            "application_key": CALLS_API_KEY,
            "session_data": json.dumps(
                {
                    "device_id": "test",
                    "version": 2,
                    "client_version": "android_8",
                    "client_type": "SDK_ANDROID",
                }
            ),
        }

        async with session.post(
            f"{CALLS_BASE_URL}/api/auth/anonymLogin", data=auth_payload
        ) as resp:
            auth_data = await resp.json()
            session_key = auth_data.get("session_key")

            if not session_key:
                return False

        lookup_payload = {
            "application_key": CALLS_API_KEY,
            "session_key": session_key,
            "externalIds": json.dumps([{"id": str(telegram_id), "ok_anonym": False}]),
        }

        async with session.post(
            f"{CALLS_BASE_URL}/api/vchat/getOkIdsByExternalIds", data=lookup_payload
        ) as resp:
            data = await resp.json()

            ids = data.get("ids", [])
            if any(
                item.get("external_user_id", {}).get("id") == str(telegram_id)
                for item in ids
            ):
                db.append(telegram_id)
                with open("db.json", "w") as f:
                    json.dump(db, f)
                save_ban_log(telegram_id)
                return True


bot = Bot(token=getenv("APIKEY"))
dp = Dispatcher()


@dp.message(Command("scan"))
async def scan(message: types.Message):
    if message.chat.type == "private":
        return
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("administrator", "creator"):
        return

    members = chat_members.get(str(message.chat.id), [])
    if not members:
        await message.reply("нет отслеживаемых участников. участники накапливаются по мере активности в чате.")
        return

    status_msg = await message.reply(f"проверяю {len(members)} участников...")
    banned = []

    for user_id in members:
        if await is_telega_user(user_id):
            try:
                await message.chat.ban(user_id)
                banned.append(user_id)
            except Exception:
                pass

    if banned:
        await status_msg.edit_text(f"заблокировано пользователей Telega: {len(banned)}\n" + "\n".join(f"id{uid}" for uid in banned))
    else:
        await status_msg.edit_text(f"проверено {len(members)} участников — пользователей Telega не найдено.")


@dp.message(Command("start"))
async def start(message: types.Message):
    if message.chat.type != "private":
        await message.react(reaction=[types.ReactionTypeEmoji(emoji="👍")])
    else:
        await message.reply(
            "я блокирую всех новых участников в твоём чате, если они пользуются Telega. подробнее о том, как это всё работает: https://github.com/hlnmplus/notelega"
        )


@dp.message()
async def check(message: types.Message):
    if message.chat.type != "private":
        track_member(message.chat.id, message.from_user.id)
    if message.chat.type == "private" and message.text.isdigit():
        await message.reply("проверяю...")
        await message.reply(
            f"id{message.text} {"является" if await is_telega_user(int(message.text)) else "не является"} пользователем Telega."
        )


@dp.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> (IS_MEMBER | ADMINISTRATOR | CREATOR)))
async def bot_added(event: types.ChatMemberUpdated):
    adder = event.from_user
    adder_mention = f"@{adder.username}" if adder.username else adder.full_name

    total = len(db)
    today = get_daily_count()

    text = (
        f"{adder_mention}, привет! Я бесплатный бот, который автоматически блокирует пользователей "
        f"Telega — кремлёвского форка Telegram.\n\n"
        f"С момента запуска я уже заблокировал {total} пользователей "
        f"(включая {today} за последние сутки).\n\n"
        f"Подробнее о принципе работы: https://github.com/hlnmplus/notelega\n\n"
        f"Сообщение будет автоматически удалено через две минуты."
    )

    msg = await bot.send_message(event.chat.id, text)
    await sleep(120)
    await msg.delete()


@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def joined(event: types.ChatMemberUpdated):
    track_member(event.chat.id, event.new_chat_member.user.id)
    if await is_telega_user(event.new_chat_member.user.id):
        await event.chat.ban(event.new_chat_member.user.id)

        note = (
            f"@{event.new_chat_member.user.username}"
            if event.new_chat_member.user.username
            else f"{event.new_chat_member.user.full_name}"
        )

        await bot.send_message(
            event.chat.id,
            f"{note} (id: {event.new_chat_member.user.id}) — пользователь Telega.",
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    run(main())
