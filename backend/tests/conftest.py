import os
from pathlib import Path

# 环境变量必须先于 app 导入生效，Settings 在导入时读取配置。
os.environ["MP_DATABASE_URL"] = "sqlite:///./data/test_backend.db"
os.environ["MP_RUN_COLLECTOR"] = "false"
os.environ["MP_COLLECTOR_MODE"] = "simulator"
os.environ["MP_FEISHU_ENABLED"] = "false"
os.environ["MP_AUTH_MODE"] = "off"
os.environ["MP_SEED_DEMO_ON_START"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    path = Path("data/test_backend.db")
    path.unlink(missing_ok=True)
    Base.metadata.create_all(bind=engine)
    init_db()
    yield
    engine.dispose()
    path.unlink(missing_ok=True)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def client(prepare_database):
    with TestClient(app) as test_client:
        yield test_client
