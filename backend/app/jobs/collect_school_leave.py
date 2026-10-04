from app.db import SessionLocal
from app.school_leave import collect_pending_school_leave, get_leave_daily_cutoff, requests_for_run


def main() -> None:
    cutoff = get_leave_daily_cutoff()
    with SessionLocal() as db:
        run = collect_pending_school_leave(db, created_by=None)
        if run is None:
            print(f"school leave collection no-op; cutoff={cutoff}")
            return
        request_count = len(requests_for_run(db, run.id))
        print(
            f"school leave collection created run={run.id}; "
            f"requests={request_count}; cutoff={cutoff}"
        )


if __name__ == "__main__":
    main()
