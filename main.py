from asyncio import run
from aiogram import types, Bot, Dispatcher
from aiogram.filters import ChatMemberUpdatedFilter
from aiogram.filters.chat_member_updated import IS_NOT_MEMBER, IS_MEMBER
from aiogram.filters.command import Command
from os import getenv
from dotenv import load_dotenv

import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()

import aiohttp
import json

CALLS_BASE_URL = getenv("CALLS_BASE_URL")
CALLS_API_KEY = getenv("CALLS_API_KEY")


async def is_telega_user(telegram_id: int) -> bool:
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
            return any(
                item.get("external_user_id", {}).get("id") == str(telegram_id)
                for item in ids
            )


bot = Bot(token=getenv("APIKEY"))
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: types.Message):
    if message.chat.type != "private":
        await message.react(reaction=[types.ReactionTypeEmoji(emoji="👍")])
    else:
        await message.reply(
            "я блокирую всех новых участников в твоём чате, если они пользуются Telega. подробнее о том, как это всё работает: https://github.com/hlnmplus/notelega"
        )


@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def joined(event: types.ChatMemberUpdated):
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
