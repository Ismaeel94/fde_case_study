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
    EVALUATE_MODE: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    APP_BASE_URL: str = "http://localhost:8000"
    REALM: str = "case_study"
    CLIENT_ID: str = "support_assistant"
    CLIENT_SECRET: str
    KEY_CLOAK_LOGIN_URL: str = "http://localhost:8080/realms/{REALM}/protocol/openid-connect/auth?client_id={CLIENT_ID}&response_type=code&scope=openid&redirect_uri={REDIRECT_URI}"
    KEY_CLOAK_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    KEYCLOAK_BASE_URL: str = "http://localhost:8080"
    KEYCLOAK_INTERNAL_URL: str = "http://keycloak:8080"
    MCP_URL: str = "http://postgres-mcp:8080/sse"
    OPENAI_API_KEY: str
    REDIS_URL: str = "redis://redis:6379/0"
    DATABASE_URL: str = "postgresql://ey_user:ey_password@postgres:5432/ey_demo"
    LANGSMITH_TRACING:str="true"
    LANGSMITH_ENDPOINT:str="https://eu.api.smith.langchain.com"
    LANGSMITH_API_KEY:str="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"
    LANGSMITH_PROJECT:str="acme"

settings = Settings()
