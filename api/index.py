import os
import tempfile

data_dir = os.path.join(tempfile.gettempdir(), "lead-validation-data")
os.environ.setdefault("DATA_DIR", data_dir)
os.environ.setdefault("DATABASE_PATH", os.path.join(data_dir, "lead_automation.sqlite3"))
os.environ.setdefault("UPLOAD_DIR", os.path.join(data_dir, "uploads"))
os.environ.setdefault("OUTPUT_DIR", os.path.join(data_dir, "outputs"))

from src.app.main import app
