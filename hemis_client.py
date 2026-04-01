import re
from typing import Dict, List

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from config import DEFAULT_TASK_ID, HEMIS_BASE_URL


class HemisClient:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logged_in = False

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def login(self, username: str, password: str) -> bool:
        if not self.page:
            await self.start()

        await self.page.goto(f"{HEMIS_BASE_URL}/", wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)

        await self.page.fill("#login", username)
        await self.page.fill("input[type='password']", password)
        await self.page.click("button[type='submit']")

        await self.page.wait_for_timeout(5000)

        current_url = self.page.url.lower()
        body = await self.page.content()

        if "login" not in current_url:
            self.logged_in = True
            return True

        if "dashboard" in current_url or "kabinet" in body.lower():
            self.logged_in = True
            return True

        self.logged_in = False
        return False

    async def get_task_page_html(self, task_id: int) -> str:
        if not self.logged_in:
            raise RuntimeError("Avval login qiling.")

        url = (
            f'{HEMIS_BASE_URL}/dashboard?drawer=task&'
            f'drawer-props=%7B%22taskId%22%3A{task_id}%7D'
        )
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(6000)
        return await self.page.content()

    async def parse_task(self, task_id: int) -> Dict:
        html = await self.get_task_page_html(task_id)
        soup = BeautifulSoup(html, "html.parser")

        text_blocks = soup.get_text("\n", strip=True).split("\n")
        clean_lines = [x.strip() for x in text_blocks if x.strip()]
        merged_text = "\n".join(clean_lines)

        subject_name = "Noma'lum fan"
        title = "Topshiriq"
        submitted = False
        graded = False
        score = ""
        deadline = ""
        expired = False

        for line in clean_lines:
            low = line.lower()

            if "sun'iy intellekt asoslari" in low or "sun’iy intellekt asoslari" in low:
                subject_name = line

            if "mustaqil ish" in low:
                title = line

            if "yuborilgan" in low:
                submitted = True

            if "baholangan" in low:
                graded = True
                submitted = True

            if "muddati" in low:
                deadline = line.replace("Muddati:", "").strip()

            if "/" in line and any(ch.isdigit() for ch in line):
                score = line.strip()

        return {
            "id": task_id,
            "subject": subject_name,
            "title": title,
            "description": merged_text[:5000],
            "submitted": submitted,
            "graded": graded,
            "score": score,
            "expired": expired,
            "deadline": deadline,
            "status": "Baholangan" if graded else ("Yuborilgan" if submitted else "Yangi"),
        }

    async def _extract_subject_links(self) -> List[str]:
        subjects_url = f"{HEMIS_BASE_URL}/dashboard/subjects"
        await self.page.goto(subjects_url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(5000)

        html = await self.page.content()
        matches = re.findall(r'/dashboard/subjects/\d+', html)

        links = []
        for m in matches:
            full = f"{HEMIS_BASE_URL}{m}"
            if full not in links:
                links.append(full)

        return links

    async def parse_subject_tasks(self, subject_url: str) -> List[Dict]:
        if not self.logged_in:
            raise RuntimeError("Avval login qiling.")

        await self.page.goto(subject_url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(5000)

        html = await self.page.content()
        soup = BeautifulSoup(html, "html.parser")

        text_blocks = soup.get_text("\n", strip=True).split("\n")
        lines = [x.strip() for x in text_blocks if x.strip()]

        subject_name = "Noma'lum fan"
        for line in lines:
            low = line.lower()
            if "dashboard" in low or "asosiy" in low or "fanlar" == low:
                continue
            if "topshiriqlar" == low or "resurslar" == low:
                continue
            if len(line) < 80 and "/" not in line and "semestr" not in low:
                subject_name = line
                break

        tasks: List[Dict] = []
        current_section = ""

        i = 0
        while i < len(lines):
            line = lines[i]
            low = line.lower()

            if "muhim topshiriqlar" in low:
                current_section = "Muhim"
                i += 1
                continue

            if "yangi topshiriqlar" in low:
                current_section = "Yangi"
                i += 1
                continue

            if "yuborilgan topshiriqlar" in low:
                current_section = "Yuborilgan"
                i += 1
                continue

            if "baholangan topshiriqlar" in low:
                current_section = "Baholangan"
                i += 1
                continue

            if "muddati o‘tgan topshiriqlar" in low or "muddati o'tgan topshiriqlar" in low:
                current_section = "Muddati o'tgan"
                i += 1
                continue

            if line == "Topshiriq":
                title = "Topshiriq"
                deadline = ""
                score = ""
                submitted = False
                graded = False
                expired = current_section == "Muddati o'tgan"

                j = i + 1
                while j < len(lines):
                    row = lines[j]
                    row_low = row.lower()

                    if row == "Topshiriq":
                        break

                    if "muhim topshiriqlar" in row_low or "yangi topshiriqlar" in row_low \
                       or "yuborilgan topshiriqlar" in row_low or "baholangan topshiriqlar" in row_low \
                       or "muddati o‘tgan topshiriqlar" in row_low or "muddati o'tgan topshiriqlar" in row_low:
                        break

                    if "mustaqil ish" in row_low:
                        title = row

                    if "muddati" in row_low:
                        deadline = row.replace("Muddati:", "").strip()

                    if "/" in row and any(ch.isdigit() for ch in row):
                        score = row.strip()

                    if "yangi" in row_low:
                        current_status = "Yangi"
                    elif "yuborilgan" in row_low:
                        current_status = "Yuborilgan"
                    elif "baholangan" in row_low:
                        current_status = "Baholangan"
                    else:
                        current_status = current_section

                    if current_status in ["Yuborilgan", "Baholangan"]:
                        submitted = True

                    if current_status == "Baholangan":
                        graded = True

                    j += 1

                tasks.append({
                    "id": None,
                    "subject": subject_name,
                    "title": title,
                    "status": current_section if current_section else "Noma'lum",
                    "submitted": submitted,
                    "graded": graded,
                    "score": score,
                    "deadline": deadline,
                    "expired": expired,
                })

                i = j
                continue

            i += 1

        return tasks

    async def parse_all_tasks(self) -> List[Dict]:
        if not self.logged_in:
            raise RuntimeError("Avval login qiling.")

        subject_links = await self._extract_subject_links()
        all_tasks: List[Dict] = []

        for subject_url in subject_links:
            try:
                subject_tasks = await self.parse_subject_tasks(subject_url)
                all_tasks.extend(subject_tasks)
            except Exception:
                continue

        if not all_tasks:
            one_task = await self.parse_task(DEFAULT_TASK_ID)
            return [one_task]

        return all_tasks

    async def upload_file_to_task(self, task_id: int, file_path: str) -> bool:
        if not self.logged_in:
            raise RuntimeError("Avval login qiling.")

        url = (
            f'{HEMIS_BASE_URL}/dashboard?drawer=task&'
            f'drawer-props=%7B%22taskId%22%3A{task_id}%7D'
        )
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(4000)

        # Keyin real upload selector topilganda to'ldiriladi
        return False