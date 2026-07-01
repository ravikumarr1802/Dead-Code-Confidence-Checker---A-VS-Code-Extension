# ============================================================
#  Dead Code Confidence Checker — Sample Test File (Python)
#  Open this in your Extension Development Host window and
#  save it to trigger the extension analysis.
# ============================================================

import os
import json
import hashlib
from typing import List, Optional, Dict


# ──────────────────────────────────────────────────────────────
#  SECTION 1: Clearly ACTIVE functions (called multiple times)
# ──────────────────────────────────────────────────────────────

class UserManager:
    """Manages user accounts — actively used throughout the app."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.users: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path) as f:
                self.users = json.load(f)

    def get_user(self, user_id: str) -> Optional[dict]:
        return self.users.get(user_id)

    def create_user(self, name: str, email: str) -> str:
        user_id = hashlib.md5(email.encode()).hexdigest()[:8]
        self.users[user_id] = {"name": name, "email": email, "active": True}
        self._save()
        return user_id

    def _save(self):
        with open(self.db_path, "w") as f:
            json.dump(self.users, f, indent=2)

    def list_active_users(self) -> List[dict]:
        return [u for u in self.users.values() if u.get("active")]


def hash_password(password: str) -> str:
    """Used in login and registration flows."""
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Called on every login attempt."""
    salt, hashed = stored_hash.split(":")
    return hashlib.sha256((password + salt).encode()).hexdigest() == hashed


def format_user_display(user: dict) -> str:
    name = user.get("name", "Unknown")
    email = user.get("email", "")
    return f"{name} <{email}>"


# ──────────────────────────────────────────────────────────────
#  SECTION 2: SUSPICIOUS functions (low call count, private)
# ──────────────────────────────────────────────────────────────

def _migrate_legacy_schema(data: dict) -> dict:
    """
    Written for v1 → v2 migration. Migration completed 8 months ago.
    Never called anymore but nobody deleted it.
    """
    if "username" in data:
        data["name"] = data.pop("username")
    if "pass" in data:
        data["password_hash"] = data.pop("pass")
    return data


def _old_hash_function(text: str) -> str:
    """Replaced by hash_password(). Left here 'just in case'."""
    return hashlib.md5(text.encode()).hexdigest()


class LegacyUserImporter:
    """
    Used to import users from the old CSV system.
    Import was completed in Q1. This whole class is likely dead.
    """

    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def parse_csv(self) -> List[dict]:
        users = []
        if not os.path.exists(self.csv_path):
            return users
        with open(self.csv_path) as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    users.append({"name": parts[0], "email": parts[1]})
        return users

    def import_all(self, manager: UserManager) -> int:
        count = 0
        for user in self.parse_csv():
            manager.create_user(user["name"], user["email"])
            count += 1
        return count

    def _validate_row(self, row: str) -> bool:
        """Private validator — only called by import_all which is itself dead."""
        return "@" in row and len(row) > 5


# ──────────────────────────────────────────────────────────────
#  SECTION 3: AMBIGUOUS functions (review needed)
# ──────────────────────────────────────────────────────────────

def send_welcome_email(email: str, name: str) -> bool:
    """
    Looks active but email service was disabled 3 months ago.
    Not called anywhere in the current codebase — but could be
    re-enabled. Classic 'review' case.
    """
    print(f"[MOCK] Sending welcome email to {name} at {email}")
    return True


def calculate_user_score(user: dict) -> float:
    """
    Was part of a recommendation engine prototype.
    The prototype was shelved but this function remains.
    """
    score = 0.0
    if user.get("active"):
        score += 10.0
    if user.get("email", "").endswith(".edu"):
        score += 5.0
    if len(user.get("name", "")) > 3:
        score += 2.0
    return score


def _temp_debug_dump(obj: object, label: str = "DEBUG") -> None:
    """Added during debugging. Definitely should be removed."""
    print(f"[{label}] {json.dumps(obj, indent=2, default=str)}")


# ──────────────────────────────────────────────────────────────
#  SECTION 4: ACTIVE utility functions (called below in main)
# ──────────────────────────────────────────────────────────────

def paginate(items: list, page: int, per_page: int = 10) -> list:
    start = (page - 1) * per_page
    return items[start: start + per_page]


def safe_get(d: dict, *keys, default=None):
    """Safely traverse nested dicts."""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d


def mask_email(email: str) -> str:
    """Used in logs to avoid printing raw emails."""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return local[:2] + "***@" + domain


# ──────────────────────────────────────────────────────────────
#  SECTION 5: Main entrypoint — calls the active functions
# ──────────────────────────────────────────────────────────────

def main():
    manager = UserManager("/tmp/test_users.json")

    # Create some users
    uid1 = manager.create_user("Alice Johnson", "alice@example.com")
    uid2 = manager.create_user("Bob Smith", "bob@university.edu")

    # Hash and verify passwords
    pw_hash = hash_password("supersecret")
    assert verify_password("supersecret", pw_hash)

    # Display users
    for user in manager.list_active_users():
        display = format_user_display(user)
        masked = mask_email(user["email"])
        print(f"  {display} — masked: {masked}")

    # Paginate
    all_users = manager.list_active_users()
    page1 = paginate(all_users, page=1, per_page=5)
    print(f"Page 1: {len(page1)} users")

    # Safe nested access
    score = safe_get({"meta": {"score": 42}}, "meta", "score", default=0)
    print(f"Score: {score}")


if __name__ == "__main__":
    main()