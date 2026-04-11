from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres@localhost:5432/forge_platform"
    app_name: str = "forge-platform"
    ai_max_tool_rounds: int = 50  # 0 = unlimited


settings = Settings()
