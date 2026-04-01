import requests
from bs4 import BeautifulSoup
from config import HEMIS_BASE_URL


class HemisClient:
    def __init__(self):
        self.session = requests.Session()
        self.logged_in = False

    async def start(self):
        return True

    async def close(self):
        self.session.close()

    async def login(self, username: str, password: str) -> bool:
        login_url = f"{HEMIS_BASE_URL}/dashboard/login"

        try:
            r = self.session.get(login_url, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            payload = {
                "FormStudentLogin[login]": username,
                "FormStudentLogin[password]": password,
            }

            csrf = soup.find("input", {"name": "_csrf-frontend"})
            if csrf:
                payload["_csrf-frontend"] = csrf.get("value")

            resp = self.session.post(login_url, data=payload, timeout=15)

            if resp.status_code == 200 and "login" not in resp.url:
                self.logged_in = True
                return True

            return False

        except Exception:
            return False

    async def parse_task(self, task_id: int):
        return {
            "id": task_id,
            "subject": "Sun'iy intellekt asoslari",
            "title": "Mustaqil ish",
            "description": "Topshiriq tavsifi",
            "submitted": False,
            "graded": False,
            "score": "",
            "deadline": "",
            "expired": False,
            "status": "Yangi",
        }

    async def parse_all_tasks(self):
        return [await self.parse_task(1)]

    async def upload_file_to_task(self, task_id: int, file_path: str) -> bool:
        return True