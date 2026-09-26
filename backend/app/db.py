import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


def _database_url() -> URL:
    return URL.create(
        "mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.environ["DB_NAME"],
        query={"charset": "utf8mb4"},
    )


engine = create_engine(_database_url(), pool_pre_ping=True)


def check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
