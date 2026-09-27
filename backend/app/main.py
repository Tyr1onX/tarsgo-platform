from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from .db import check_database
from .routers import ai_planner, auth, invitations, members, tasks

app = FastAPI(title="TARS-Go Platform API")
app.include_router(auth.router)
app.include_router(invitations.router)
app.include_router(members.router)
app.include_router(tasks.router)
app.include_router(ai_planner.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        check_database()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}
