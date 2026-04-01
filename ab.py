import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from ai_generator import generate_with_ai
from config import ADMIN_USER_ID, BOT_TOKEN, DATA_DIR, PDF_DIR, DEFAULT_TASK_ID
from hemis_client import HemisClient
from pdf_builder import build_pdf
from training_manager import load_subject, save_subject


Path(DATA_DIR).mkdir(exist_ok=True)
Path(PDF_DIR).mkdir(exist_ok=True)

bot = Bot(token=BOT_TOKEN.strip())
dp = Dispatcher()

user_data = {}
hemis = HemisClient()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID


def get_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Barcha topshiriqlar")],
            [KeyboardButton(text="🧠 O‘qitish rejimi")],
            [KeyboardButton(text="📝 MI tayyorlash")],
            [KeyboardButton(text="📤 HEMIS ga yuklash")],
            [KeyboardButton(text="🤖 Auto agent")],
            [KeyboardButton(text="♻️ Qayta login"), KeyboardButton(text="🚪 Chiqish")],
        ],
        resize_keyboard=True,
    )


def format_task_status(task: dict) -> str:
    if task.get("status"):
        return task["status"]

    parts = []
    if task.get("submitted"):
        parts.append("Yuklangan")
    else:
        parts.append("Yuklanmagan")

    if task.get("graded"):
        parts.append("Baholangan")
    else:
        parts.append("Baholanmagan")

    if task.get("expired"):
        parts.append("Muddati o'tgan")

    return ", ".join(parts)


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Sizga ruxsat yo'q.")
        return

    user_data[message.from_user.id] = {"step": "login"}
    await message.answer(
        "🔐 HEMIS login kiriting:",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Command("id"))
async def id_handler(message: types.Message):
    await message.answer(f"Sizning Telegram ID: {message.from_user.id}")


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    if not is_admin(user_id):
        await message.answer("Sizga ruxsat yo'q.")
        return

    if user_id not in user_data:
        user_data[user_id] = {"step": "login"}
        await message.answer(
            "🔐 HEMIS login kiriting:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    step = user_data[user_id].get("step")

    if step == "login":
        user_data[user_id]["login"] = text
        user_data[user_id]["step"] = "password"
        await message.answer("🔑 HEMIS parol kiriting:")
        return

    if step == "password":
        login = user_data[user_id].get("login", "")
        password = text

        msg = await message.answer("⏳ Tekshirilmoqda...")

        try:
            success = await hemis.login(login, password)
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik: {e}")
            user_data[user_id]["step"] = "login"
            return

        if success:
            user_data[user_id]["step"] = "menu"
            await msg.edit_text("✅ HEMIS login muvaffaqiyatli!")
            await message.answer("Asosiy menyu:", reply_markup=get_menu())
        else:
            user_data[user_id]["step"] = "login"
            await msg.edit_text("❌ Login yoki parol noto‘g‘ri!")
            await message.answer(
                "🔐 Qaytadan HEMIS login kiriting:",
                reply_markup=ReplyKeyboardRemove(),
            )
        return

    if text == "♻️ Qayta login":
        user_data[user_id] = {"step": "login"}
        await message.answer(
            "🔐 HEMIS login kiriting:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if text == "🚪 Chiqish":
        user_data[user_id] = {"step": "login"}
        user_data[user_id].pop("tasks", None)
        user_data[user_id].pop("selected_task", None)
        user_data[user_id].pop("generated_pdf", None)
        await message.answer(
            "Sessiya tozalandi. 🔐 HEMIS login kiriting:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if step == "menu":
        if text == "📋 Barcha topshiriqlar":
            wait = await message.answer("⏳ Topshiriqlar yuklanmoqda...")

            try:
                tasks = await hemis.parse_all_tasks()
            except Exception as e:
                await wait.edit_text(f"❌ Xatolik: {e}")
                return

            if not tasks:
                await wait.edit_text("Topshiriqlar topilmadi.")
                return

            user_data[user_id]["tasks"] = tasks
            user_data[user_id]["step"] = "await_task_choice"

            text_out = "📚 Topshiriqlar ro'yxati:\n\n"

            for i, t in enumerate(tasks, 1):
                subject = t.get("subject", "Noma’lum fan")
                title = t.get("title", "Topshiriq")
                status = format_task_status(t)

                text_out += f"{i}. {subject} | {title}\n"
                text_out += f"Holat: {status}\n"

                if t.get("score"):
                    text_out += f"Ball: {t['score']}\n"

                if t.get("deadline"):
                    text_out += f"Muddat: {t['deadline']}\n"

                text_out += "\n"

            text_out += "Tanlash uchun raqam yuboring."

            if len(text_out) > 4000:
                text_out = text_out[:4000] + "\n..."

            await wait.edit_text(text_out)
            return

        if text == "🧠 O‘qitish rejimi":
            user_data[user_id]["step"] = "training_subject"
            await message.answer("Qaysi fan uchun o‘qitmoqchisiz?")
            return

        if text == "📝 MI tayyorlash":
            selected_task = user_data[user_id].get("selected_task")
            if not selected_task:
                await message.answer("Avval 📋 Barcha topshiriqlar bo‘limidan topshiriq tanlang.")
                return

            subject_name = selected_task.get("subject", "Noma'lum fan")
            task_title = selected_task.get("title", "Topshiriq")

            wait = await message.answer("⏳ Mustaqil ish tayyorlanmoqda...")

            try:
                task_detail = await hemis.parse_task(DEFAULT_TASK_ID)
                training_data = load_subject(subject_name)

                result_text = await generate_with_ai(
                    task_text=task_detail["description"],
                    subject_name=subject_name,
                    task_title=task_title,
                    training_data=training_data,
                )

                pdf_buffer = build_pdf(result_text)
                file_name = f"{task_title.replace(' ', '_')}.pdf"
                output_path = Path(PDF_DIR) / file_name

                with open(output_path, "wb") as f:
                    f.write(pdf_buffer.getvalue())

                user_data[user_id]["generated_pdf"] = str(output_path)

                pdf = BufferedInputFile(output_path.read_bytes(), filename=file_name)
                await message.answer_document(
                    document=pdf,
                    caption=(
                        f"✅ Tayyor bo‘ldi.\n"
                        f"Fan: {subject_name}\n"
                        f"Topshiriq: {task_title}"
                    ),
                )

                await wait.delete()

            except Exception as e:
                await wait.edit_text(f"❌ Xatolik: {e}")
            return

        if text == "📤 HEMIS ga yuklash":
            if "generated_pdf" not in user_data[user_id]:
                await message.answer("Avval 📝 MI tayyorlash ni bosing.")
                return

            await message.answer(
                "📤 Upload skeleti tayyor.\n"
                "Real upload selector topilgach shu bo‘lim ishlaydi."
            )
            return

        if text == "🤖 Auto agent":
            await message.answer(
                "🤖 Auto agent hozircha skelet holatda.\n"
                "Keyin u yuklanmagan topshiriqlarni topib, AI bilan tayyorlab, HEMIS ga yuklaydi."
            )
            return

        await message.answer("Noto‘g‘ri buyruq.")
        return

    if step == "await_task_choice":
        tasks = user_data[user_id].get("tasks", [])

        if not text.isdigit():
            await message.answer("Faqat raqam yuboring.")
            return

        idx = int(text) - 1
        if idx < 0 or idx >= len(tasks):
            await message.answer("Noto‘g‘ri raqam.")
            return

        selected_task = tasks[idx]
        user_data[user_id]["selected_task"] = selected_task
        user_data[user_id]["step"] = "menu"

        await message.answer(
            f"✅ Tanlandi:\n"
            f"Fan: {selected_task.get('subject', 'Noma’lum fan')}\n"
            f"Topshiriq: {selected_task.get('title', 'Topshiriq')}\n"
            f"Holat: {format_task_status(selected_task)}\n\n"
            f"Endi 📝 MI tayyorlash ni bosing.",
            reply_markup=get_menu(),
        )
        return

    if step == "training_subject":
        user_data[user_id]["training_subject"] = text
        user_data[user_id]["step"] = "training_title_template"
        await message.answer("Titul/shablon matnini yuboring.")
        return

    if step == "training_title_template":
        subject = user_data[user_id]["training_subject"]
        data = load_subject(subject)
        data["title_template"] = text
        save_subject(subject, data)

        user_data[user_id]["step"] = "training_samples"
        await message.answer("Namuna MI matnini yuboring. Tugatgach DONE deb yozing.")
        return

    if step == "training_samples":
        subject = user_data[user_id]["training_subject"]

        if text.upper() == "DONE":
            user_data[user_id]["step"] = "menu"
            data = load_subject(subject)
            await message.answer(
                f"✅ O‘qitish tugadi.\n"
                f"Fan: {subject}\n"
                f"Namuna soni: {len(data['samples'])}",
                reply_markup=get_menu(),
            )
            return

        data = load_subject(subject)
        data["samples"].append(text)
        save_subject(subject, data)
        await message.answer("Namuna qo‘shildi. Yana yuboring yoki DONE yozing.")
        return


async def main():
    print("Bot ishga tushdi...")
    await hemis.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())