import os

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/aether_pytest.db")
os.environ.setdefault("SANDBOX_BACKEND", "subprocess")
