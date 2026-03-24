from asyncio import run
from aiogram import types, Bot, Dispatcher, F
from aiogram.filters import ChatMemberUpdatedFilter
from aiogram.filters.chat_member_updated import IS_NOT_MEMBER, IS_MEMBER
from aiogram.types import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    ChatMemberAdministrator,
)
from aiogram.filters.command import Command
from os import getenv
from dotenv import load_dotenv

load_dotenv()

from checker import TelegaChecker

bot = Bot(token=getenv("APIKEY"))
dp = Dispatcher()

checker = TelegaChecker()


@dp.message(Command("start"))
async def start(message: types.Message):
    if message.chat.type != "private":
        await message.react(reaction=[types.ReactionTypeEmoji(emoji="👍")])
    else:
        await message.reply(
            "я блокирую всех новых участников в твоём чате, если они пользуются Telega. подробнее о том, как это всё работает: https://github.com/hlnmplus/notelega"
        )


@dp.message(Command("istelega"))
async def start(message: types.Message):
    if len(message.text.split()) > 1:
        id = message.text.split()[1]
    else:
        await message.reply("укажи id после команды, например: /istelega 5224925247")
        return
    if not id.isdigit():
        await message.reply("id должен быть числом, например: /istelega 5224925247")
        return
    await message.reply("проверяю...")
    await message.reply(
        f"{id}{'' if await checker.is_telega_user(int(id)) else ' не'} является пользователем Telega."
    )


@dp.message()
async def check(message: types.Message):
    if message.chat.type == "private" and message.text and message.text.isdigit():
        await message.reply("проверяю...")
        await message.reply(
            f"{message.text}{'' if await checker.is_telega_user(int(message.text)) else ' не'} является пользователем Telega."
        )


@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def joined(event: types.ChatMemberUpdated):
    if await checker.is_telega_user(event.new_chat_member.user.id):
        me = await event.bot.get_chat_member(event.chat.id, await event.bot.get_me().id)
        if type(me) == ChatMemberAdministrator and me.can_restrict_members == True:
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


@dp.inline_query(F.query.regexp(r"^\d+$"))
async def inline_check_id(query: types.InlineQuery):
    user_id = int(query.query)
    is_telega = await checker.is_telega_user(user_id)
    if is_telega:
        title = f"{user_id} — пользователь Telega ❌"
        text = f"{user_id} является пользователем Telega ❌"
    else:
        title = f"{user_id} — не пользователь Telega ✅"
        text = f"{user_id} не является пользователем Telega ✅"
    await query.answer(
        results=[
            InlineQueryResultArticle(
                id=str(user_id),
                title=title,
                input_message_content=InputTextMessageContent(message_text=text),
            )
        ],
        cache_time=60,
    )


@dp.inline_query()
async def inline_hint(query: types.InlineQuery):
    await query.answer(
        results=[
            InlineQueryResultArticle(
                id="hint",
                title="введите Telegram ID для проверки",
                description="например: 5224925247",
                input_message_content=InputTextMessageContent(
                    message_text="для проверки введите числовой Telegram ID после имени бота."
                ),
            )
        ],
        cache_time=0,
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    run(main())
