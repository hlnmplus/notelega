import aiohttp
import json
import os
from typing import List

CALLS_BASE_URL = os.getenv("CALLS_BASE_URL")
CALLS_API_KEY = os.getenv("CALLS_API_KEY")


class TelegaChecker:
    def __init__(self, db_path: str = "db.json"):
        self.db_path = db_path
        self.cached_session_key = None
        self._load_db()

    def _load_db(self):
        try:
            with open(self.db_path) as f:
                self.db: List[int] = json.load(f)
        except FileNotFoundError:
            self.db = []

    def _save_db(self):
        with open(self.db_path, "w") as f:
            json.dump(self.db, f)

    async def is_telega_user(self, telegram_id: int) -> bool:
        if telegram_id in self.db:
            return True

        while True:
            if self.cached_session_key is None:
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
                        self.cached_session_key = auth_data.get("session_key")

                        if not self.cached_session_key:
                            return False

            async with aiohttp.ClientSession() as session:
                lookup_payload = {
                    "application_key": CALLS_API_KEY,
                    "session_key": self.cached_session_key,
                    "externalIds": json.dumps(
                        [{"id": str(telegram_id), "ok_anonym": False}]
                    ),
                }

                async with session.post(
                    f"{CALLS_BASE_URL}/api/vchat/getOkIdsByExternalIds",
                    data=lookup_payload,
                ) as resp:
                    data = await resp.json()

                    ids = data.get("ids", [])
                    error_code = data.get("error_code")

                    if not ("ids" in data or data.get("error_code") == 4):
                        self.cached_session_key = None
                        continue

                    if any(
                        item.get("external_user_id", {}).get("id") == str(telegram_id)
                        for item in ids
                    ):
                        self.db.append(telegram_id)
                        self._save_db()
                        return True
                    return False
