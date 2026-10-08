import os
import tempfile
import atexit
import shutil

# Create a temporary directory that lasts for the whole test session
test_data_dir = tempfile.mkdtemp(prefix="rag_test_data_")

# Set the environment variable BEFORE any app modules are imported
os.environ["DATA_DIR"] = test_data_dir

def cleanup():
    shutil.rmtree(test_data_dir, ignore_errors=True)

atexit.register(cleanup)
