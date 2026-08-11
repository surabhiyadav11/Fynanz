import time
from datetime import timezone, datetime
import uuid
from pymongo import MongoClient, errors as mongodb_errors

from utils import generate_token


def simple_log(message: str):
    print(f"[MongoDB]: {message}")


class MongoDBClient:
    """
    Simple MongoDB connection manager with auto-reconnect
    """

    def __init__(
        self,
        connection_uri: str,
        db_name: str,
        max_retries: int = 5,
        retry_delay: int = 3,
    ):
        self.uri = connection_uri
        self.db_name = db_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.client = None
        self.db = None

        self.connect()  # Connect for the first time

    def connect(self):
        """Connect the MongoDB server with simple retry logic"""
        retries = 0
        while retries < self.max_retries:
            try:
                simple_log(f"(Attempt {retries + 1}) Connecting...")
                self.client = MongoClient(
                    self.uri,
                    tz_aware=True,  # Required for proper timezone comparison
                    tzinfo=timezone.utc,  # Required for proper timezone comparison
                    serverSelectionTimeoutMS=4000,
                )

                self.client.admin.command("ping")  # Ping the server

                self.db = self.client[self.db_name]
                simple_log("Connection successful!")

                return

            except mongodb_errors.ConnectionFailure:
                simple_log("Connection failed. Retrying...")
                retries += 1
                time.sleep(self.retry_delay)

        raise RuntimeError(
            "Could not connect to the MongoDB server after multiple attempts"
        )

    def get_collection(self, name: str):
        """Connect the MongoDB server with simple auto reconnect logic"""
        try:
            self.client.admin.command("ping")  # Ping before returning the collection
            return self.db[name]
        except mongodb_errors.PyMongoError:
            simple_log("Lost connection. Reconnecting...")
            self.connect()
            return self.db[name]

    def find_user(self, query: dict, include_password=False):
        users = self.get_collection("users")
        include = {"_id": 0}
        if not include_password:
            include["password"] = 0
        return users.find_one(query, include)

    def insert_new_user(self, user_data: dict):
        users = self.get_collection("users")
        new_user_data = {**user_data, "user_id": str(uuid.uuid4())}
        return users.insert_one(new_user_data)

    def delete_user(self, query: dict):
        results = []
        users = self.get_collection("users")
        sessions = self.get_collection("sessions")

        results.append(users.delete_one(query))
        results.append(sessions.delete_one(query))

        return results

    def find_session(self, query: dict):
        sessions = self.get_collection("sessions")
        return sessions.find_one(query, {"_id": 0})

    def create_session(self, session_data: dict, expiry):
        sessions = self.get_collection("sessions")
        new_session_data = {
            **session_data,
            "session_id": generate_token(),
            "csrf_token": generate_token(),
            "expires_at": expiry,
        }
        return sessions.insert_one(new_session_data)

    def delete_session(self, query):
        sessions = self.get_collection("sessions")
        return sessions.delete_one(query)

    def update_login_streak(self, user_id: str):
        """Update or create login streak for a user"""
        from datetime import datetime, timedelta

        streaks = self.get_collection("streaks")
        streak_data = streaks.find_one({"user_id": user_id})

        today = datetime.now().date()

        if not streak_data:
            new_streak = {
                "user_id": user_id,
                "current_streak": 1,
                "longest_streak": 1,
                "last_login": today.isoformat(),
            }
            streaks.insert_one(new_streak)
            return new_streak
        else:
            last_login = datetime.fromisoformat(streak_data["last_login"]).date()

            if last_login == today:
                return streak_data
            elif last_login == today - timedelta(days=1):
                new_current = streak_data["current_streak"] + 1
                new_longest = max(streak_data["longest_streak"], new_current)

                streaks.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "current_streak": new_current,
                            "longest_streak": new_longest,
                            "last_login": today.isoformat(),
                        }
                    },
                )
                return {
                    "user_id": user_id,
                    "current_streak": new_current,
                    "longest_streak": new_longest,
                    "last_login": today.isoformat(),
                }
            else:
                streaks.update_one(
                    {"user_id": user_id},
                    {"$set": {"current_streak": 1, "last_login": today.isoformat()}},
                )
                return {
                    "user_id": user_id,
                    "current_streak": 1,
                    "longest_streak": streak_data["longest_streak"],
                    "last_login": today.isoformat(),
                }

    def get_user_streak(self, user_id: str):
        """Get login streak for a user"""
        streaks = self.get_collection("streaks")
        streak_data = streaks.find_one({"user_id": user_id}, {"_id": 0})
        return (
            streak_data
            if streak_data
            else {
                "user_id": user_id,
                "current_streak": 0,
                "longest_streak": 0,
                "last_login": None,
            }
        )

    def add_badge(self, user_id: str, badge_name: str, badge_data: dict):
        """Add a badge to user"""
        badges = self.get_collection("badges")

        existing = badges.find_one(
            {"user_id": user_id, "badge_name": badge_name}, {"_id": 0}
        )
        if existing:
            return existing

        new_badge = {
            "user_id": user_id,
            "badge_name": badge_name,
            "earned_at": datetime.now().isoformat(),
            **badge_data,
        }
        badges.insert_one(new_badge)
        return {k: v for k, v in new_badge.items() if k != "_id"}

    def get_user_badges(self, user_id: str):
        """Get all badges for a user"""
        badges = self.get_collection("badges")
        user_badges = list(badges.find({"user_id": user_id}, {"_id": 0}))
        return user_badges
