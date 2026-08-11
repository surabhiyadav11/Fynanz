import os
from dotenv import load_dotenv

# Load all the environment variables from the .env file otherwise load them from example .env file if not found:
if not load_dotenv(".env"):
    load_dotenv(".env.example")

MONGODB_CONNECTION_URI = os.getenv(
    "MONGODB_CONNECTION_URI", "mongodb://localhost:27017/"
)

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DB_NAME = os.getenv("MYSQL_DB_NAME", "data")

SESSION_EXPIRY = 15  # Session ID and Token expiry (in days)

# CORS configuration - specify exact origins when using credentials
# For development, includes common localhost ports used by Live Server and dev servers
ALLOWED_ORIGINS = [
    "http://localhost:8000",  # FastAPI docs
    "http://localhost:3000",  # Common dev port
    "http://localhost:5500",  # Live Server default port
    "http://localhost:5501",  # Live Server fallback port
    "http://localhost:8080",  # Common dev port
    "http://127.0.0.1:5500",  # Live Server with 127.0.0.1
    "http://127.0.0.1:5501",  # Live Server fallback with 127.0.0.1
    "https://fynanz.vercel.app",  # Production frontend on Vercel
    os.getenv("FRONTEND_URL", "http://localhost:5500"),  # Configurable via env
]
