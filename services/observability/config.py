import os


class Settings:
    def __init__(self) -> None:
        # Vercel's filesystem is read-only except /tmp (per-instance, ephemeral).
        default_path = "/tmp/trace_logs.db" if os.getenv("VERCEL") else "trace_logs.db"
        self.db_path = os.getenv("TRACE_DB_PATH", default_path)


settings = Settings()
