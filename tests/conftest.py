import os
import tempfile
import atexit
import shutil

# Create a temporary directory that lasts for the whole test session
test_data_dir = tempfile.mkdtemp(prefix="rag_test_data_")

# Set the environment variable BEFORE any app modules are imported
os.environ["DATA_DIR"] = test_data_dir
# Retrieval tests stub embed_texts with 384-dim vectors.
os.environ.setdefault("EMBEDDING_DIM", "384")
# Upload routes are exercised directly; production defaults them off.
os.environ.setdefault("KNOWLEDGE_UPLOADS_ENABLED", "true")

def cleanup():
    shutil.rmtree(test_data_dir, ignore_errors=True)

atexit.register(cleanup)
