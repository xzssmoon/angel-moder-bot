import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, ChatPermissions, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
MODERATORS = []
ROLES = ["Новичок", "Участник", "Модератор", "Ст. модератор", "Админ"]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WARNS = {}
REPS = {}
ROLES_DB = {}
MUTES = {}
BANS = {}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID or user_id in MODERATORS


def get_target(message: Message):
    if message.reply_to_message:
        u = message.reply_to_message.from_user
        return u.id, u.full_name

    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        try:
            uid = int(parts[1].strip())
            return uid, f"ID {uid}"
        except ValueError:
            return None, None
    return None, None


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 <b>ModerBot</b> на связи.\n\n"
        "/ban — забанить (реплай)\n"
        "/unban — разбанить\n"
        "/mute 10 — мут на 10 минут\n"
        "/warn — выговор\n"
        "/rep + или /rep -\n"
        "/promote — повысить\n"
        "/demote — понизить\n"
        "/admin — админ-панель",
        parse_mode="HTML"
    )


@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="👥 Роли", callback_data="adm_roles")],
        [InlineKeyboardButton(text="⚠️ Выговоры", callback_data="adm_warns")],
        [InlineKeyboardButton(text="⭐ Топ репы", callback_data="adm_reps")],
    ])

    await message.answer(
        "🛠 <b>Админ-панель</b>\n\n"
        "/ban /unban /mute /warn /rep /promote /demote",
        reply_markup=kb,
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.answer(
        f"📊 Статистика\n\n"
        f"Выговоров: {sum(WARNS.values())}\n"
        f"Забанено: {len(BANS)}\n"
        f"В муте: {len(MUTES)}\n"
        f"Юзеров с репой: {len(REPS)}"
    )
    await call.answer()


@dp.callback_query(F.data == "adm_roles")
async def adm_roles(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    text = "👥 Роли\n\n"
    if not ROLES_DB:
        text += "Пусто."
    else:
        for uid, idx in ROLES_DB.items():
            text += f"• {uid} — {ROLES[idx]}\n"
    await call.message.answer(text)
    await call.answer()


@dp.callback_query(F.data == "adm_warns")
async def adm_warns(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    text = "⚠️ Выговоры\n\n"
    if not WARNS:
        text += "Пусто."
    else:
        for uid, cnt in WARNS.items():
            text += f"• {uid} — {cnt}\n"
    await call.message.answer(text)
    await call.answer()


@dp.callback_query(F.data == "adm_reps")
async def adm_reps(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if not REPS:
        await call.message.answer("Репутаций нет.")
    else:
        top = sorted(REPS.items(), key=lambda x: x[1], reverse=True)[:10]
        text = "⭐ Топ репутации\n\n"
        for uid, score in top:
            text += f"• {uid} — {score}\n"
        await call.message.answer(text)
    await call.answer()


@dp.message(Command("ban"))
async def ban_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    uid, name = get_target(message)
    if not uid:
        await message.answer("Использование: реплай или /ban ID")
        return
    try:
        await bot.ban_chat_member(message.chat.id, uid)
        BANS[uid] = True
        await message.answer(f"🔨 Забанен: {name}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("unban"))
async def unban_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    uid, name = get_target(message)
    if not uid:
        await message.answer("Использование: /unban ID")
        return
    try:
        await bot.unban_chat_member(message.chat.id, uid)
        BANS.pop(uid, None)
        await message.answer(f"✅ Разбанен: {name}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("mute"))
async def mute_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    minutes = 10
    if len(parts) > 1 and parts[1].isdigit():
        minutes = int(parts[1])

    uid, name = get_target(message)
    if not uid:
        await message.answer("Использование: реплай + /mute 10")
        return

    until = datetime.now() + timedelta(minutes=minutes)
    MUTES[uid] = until
    try:
        await bot.restrict_chat_member(
            message.chat.id, uid,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await message.answer(f"🔇 {name} в муте на {minutes} мин.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("warn"))
async def warn_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    uid, name = get_target(message)
    if not uid:
        await message.answer("Использование: реплай или /warn ID")
        return

    WARNS[uid] = WARNS.get(uid, 0) + 1
    cnt = WARNS[uid]
    await message.answer(f"⚠️ {name} получил выговор. Всего: {cnt}")

    if cnt >= 3:
        try:
            await bot.ban_chat_member(message.chat.id, uid)
            BANS[uid] = True
            await message.answer(f"🔨 {name} автобан (3 выговора).")
        except Exception as e:
            await message.answer(f"❌ Не удалось забанить: {e}")


@dp.message(Command("rep"))
async def rep_cmd(message: Message):
    parts = message.text.split()
    if len(parts) < 2 or parts[1] not in ("+", "-"):
        await message.answer("Использование: /rep + или /rep - (в реплае)")
        return
    if not message.reply_to_message:
        await message.answer("Нужен реплай.")
        return

    uid = message.reply_to_message.from_user.id
    if uid == message.from_user.id:
        await message.answer("❌ Себе нельзя.")
        return

    delta = 1 if parts[1] == "+" else -1
    REPS[uid] = REPS.get(uid, 0) + delta
    await message.answer(f"⭐ Репутация: {REPS[uid]}")


@dp.message(Command("promote"))
async def promote_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    uid, name = get_target(message)
    if not uid:
        await message.answer("Использование: реплай + /promote")
        return

    current = ROLES_DB.get(uid, 0)
    if current >= len(ROLES) - 1:
        await message.answer("Уже максимум.")
        return

    ROLES_DB[uid] = current + 1
    await message.answer(f"⬆️ {name} → {ROLES[ROLES_DB[uid]]}")


@dp.message(Command("demote"))
async def demote_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    uid, name = get_target(message)
    if not uid:
        await message.answer("Использование: реплай + /demote")
        return

    current = ROLES_DB.get(uid, 0)
    if current <= 0:
        await message.answer("Уже минимум.")
        return

    ROLES_DB[uid] = current - 1
    await message.answer(f"⬇️ {name} → {ROLES[ROLES_DB[uid]]}")


async def main():
    print("ModerBot запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
