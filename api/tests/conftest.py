import os
import tempfile

# Isolate every test run: settings and the DB engine are created at import time.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="jobagent-test-")
os.environ["SECRET_KEY"] = "test-secret"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")
