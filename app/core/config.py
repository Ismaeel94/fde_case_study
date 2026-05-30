from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "FDE Case Study API"
    API_V1_PREFIX: str = ""
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    REALM: str= "case_study"
    CLIENT_ID: str = "support_assistant"
    CLIENT_SECRET:str
    KEY_CLOAK_LOGIN_URL: str = "http://localhost:8080/realms/{REALM}/protocol/openid-connect/auth?client_id={CLIENT_ID}&response_type=code&scope=openid&redirect_uri={REDIRECT_URI}"
    KEY_CLOAK_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    KEYCLOAK_BASE_URL: str = "http://localhost:8080"
    MCP_URL: str = "http://localhost:8081/sse"
    OPENAI_API_KEY: str


settings = Settings()
