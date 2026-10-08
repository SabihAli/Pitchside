import os


class Settings:
    def __init__(self) -> None:
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION", "futbot_chunks")
        self.data_dir = os.getenv("DATA_DIR", "data")
        self.chroma_path = os.path.join(self.data_dir, "chroma_db")
        self.bm25_path = os.path.join(self.data_dir, "bm25_index.pkl")
        self.dense_top_k = int(os.getenv("RETRIEVAL_DENSE_TOP_K", "15"))
        self.sparse_top_k = int(os.getenv("RETRIEVAL_SPARSE_TOP_K", "15"))
        self.default_top_k = int(os.getenv("RETRIEVAL_DEFAULT_TOP_K", "5"))


settings = Settings()
