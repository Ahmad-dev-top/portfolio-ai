"""Settings loaded from .env — the only place secrets are read."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    admin_secret: str
    admin_pass_hash: str

    allowed_origins: str = "http://localhost:5500"
    db_path: str = "./data/portfolio.db"
    site_path: str = "./site"

    # Optional: commit Studio content to GitHub on every Apply
    github_sync_enabled: bool = False
    github_token: str = ""
    github_repo: str = ""  # owner/repo e.g. Ahmad-dev-top/my-portfolio
    github_branch: str = "main"
    github_content_path: str = "site/content.json"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
