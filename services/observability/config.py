import os


class Settings:
    def __init__(self) -> None:
        self.db_path = os.getenv("TRACE_DB_PATH", "trace_logs.db")


settings = Settings()
