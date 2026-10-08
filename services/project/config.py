import os


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://futbot:futbot@localhost:5432/futbot"
        )
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY", "futbot")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY", "futbotminio")
        self.minio_bucket = os.getenv("MINIO_BUCKET", "futbot-projects")
        self.minio_secure = os.getenv("MINIO_SECURE", "false").lower() in {
            "1",
            "true",
            "yes",
        }
        self.ingestion_service_url = os.getenv(
            "INGESTION_SERVICE_URL", "http://localhost:8086"
        )


settings = Settings()
