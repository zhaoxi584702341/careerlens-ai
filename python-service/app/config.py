import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_name: str = "careerlens-ai-python"
    backend_base_url: str = os.getenv("BACKEND_BASE_URL", "http://localhost:8081")


settings = Settings()
