import os
from dotenv import load_dotenv
load_dotenv(override=True)

JWT_SECRET = os.getenv("JWT_SECRET", "paseseguro2026clave")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "paseseguro2026")
DB_PATH = os.getenv("DB_PATH", "vehicles.db")
