from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://provereno:provereno@localhost:5434/provereno"
    github_client_id: str = ""
    github_client_secret: str = ""
    session_secret_key: str = "dev_secret_change_me"
    allowed_github_orgs: str = ""
    allowed_github_logins: str = ""
    data_dir: str = "./data"

settings = Settings()
