import json
from pathlib import Path

from config import DATA_DIR


Path(DATA_DIR).mkdir(exist_ok=True)


def subject_file(subject_name: str) -> Path:
    safe_name = (
        subject_name.strip()
        .lower()
        .replace(" ", "_")
        .replace("’", "")
        .replace("'", "")
    )
    return Path(DATA_DIR) / f"{safe_name}.json"


def load_subject(subject_name: str) -> dict:
    path = subject_file(subject_name)

    if not path.exists():
        return {
            "subject": subject_name,
            "title_template": "",
            "samples": [],
            "topics": [],
        }

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_subject(subject_name: str, data: dict):
    path = subject_file(subject_name)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def list_subjects() -> list[str]:
    subjects = []

    for file in Path(DATA_DIR).glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                subjects.append(data.get("subject", file.stem))
        except Exception:
            continue

    return subjects