from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from .db import check_database

app = FastAPI(title="TARS-Go Platform API")


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        check_database()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    return {"status": "ok"}
