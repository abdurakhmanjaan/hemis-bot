import aiohttp

from config import AI_API_KEY, AI_API_URL


async def generate_with_ai(
    task_text: str,
    subject_name: str,
    task_title: str,
    training_data: dict,
) -> str:
    title_template = training_data.get("title_template", "")
    samples = training_data.get("samples", [])

    prompt = f"""
Quyidagi topshiriq asosida o'zbek lotin yozuvida mustaqil ish yozing.

Fan:
{subject_name}

Topshiriq nomi:
{task_title}

Titul namunasi:
{title_template}

Namuna matnlar:
{chr(10).join(samples[-2:]) if samples else "Namuna yo'q"}

Talablar:
- 6 betdan kam bo'lmasin
- Titul
- Reja
- Asosiy qism
- Xulosa
- Foydalanilgan adabiyotlar
- Tartibli rasmiy uslub

Topshiriq matni:
{task_text}
"""

    if AI_API_URL.startswith("https://example.com"):
        return f"""
TITUL

Fan: {subject_name}
Mavzu: {task_title}

REJA
1. Kirish
2. Asosiy qism
3. Xulosa
4. Foydalanilgan adabiyotlar

KIRISH
Ushbu mustaqil ish {subject_name} faniga oid topshiriq asosida tayyorlandi.

ASOSIY QISM
Mazkur topshiriq matni asosida mavzu yoritiladi:
{task_text[:2500]}

Namuna uslubi:
{samples[-1] if samples else "Namuna hali yuklanmagan."}

XULOSA
Mazkur topshiriq bo'yicha nazariy va amaliy jihatlar yoritildi.

FOYDALANILGAN ADABIYOTLAR
1. Darsliklar
2. O'quv qo'llanmalar
3. Internet manbalari
"""

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt}

    async with aiohttp.ClientSession() as session:
        async with session.post(AI_API_URL, json=payload, headers=headers, timeout=180) as resp:
            if resp.status != 200:
                raise Exception(f"AI API xatolik: {resp.status}")

            data = await resp.json()
            return data.get("text", "AI matn qaytarmadi")