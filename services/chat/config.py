import os


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://futbot:futbot@localhost:5432/futbot"
        )
        self.project_service_url = os.getenv(
            "PROJECT_SERVICE_URL", "http://localhost:8083"
        )
        self.hot_context_window = int(os.getenv("HOT_CONTEXT_WINDOW", "10"))
        self.context_budget_tokens = int(os.getenv("CONTEXT_BUDGET_TOKENS", "8192"))
        self.auto_compress_threshold_pct = int(
            os.getenv("AUTO_COMPRESS_THRESHOLD_PCT", "85")
        )
        self.llm_gateway_url = os.getenv("LLM_GATEWAY_URL", "http://localhost:8087")
        self.orchestrator_service_url = os.getenv(
            "ORCHESTRATOR_SERVICE_URL", "http://localhost:8084"
        )
        self.tools_service_url = os.getenv("TOOLS_SERVICE_URL", "http://localhost:8088")
        self.snapshot_max_tokens = int(os.getenv("SNAPSHOT_MAX_TOKENS", "300"))


settings = Settings()
