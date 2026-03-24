from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:forge-secret-password@forge-postgresql.forge-platform.svc.cluster.local:5432/forge_platform"
    app_name: str = "forge-platform"


settings = Settings()
