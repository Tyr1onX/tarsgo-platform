from app.db import SessionLocal
from app.school_leave import cleanup_expired_school_leave_results


def main() -> None:
    with SessionLocal() as db:
        cleaned = cleanup_expired_school_leave_results(db)
    print(f"school leave result cleanup removed={cleaned}")


if __name__ == "__main__":
    main()
