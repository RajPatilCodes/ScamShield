import argparse
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from .database import SessionLocal
from .privacy_config import policy
from .privacy_models import PrivacyJob
from .privacy_jobs import process_job, sweep, retry_marker, retry_job
from .ownership import require_authority, initialise_authority, reconcile_authority


def run_once(factory=SessionLocal, purge=True):
    with factory() as db:
        require_authority(db)
        jobs = list(db.scalars(select(PrivacyJob.id).where(PrivacyJob.state.in_(["queued", "retrying"]),
            PrivacyJob.next_attempt_at <= int(time.time())).order_by(PrivacyJob.created_at, PrivacyJob.id).limit(policy.batch_size)))
    processed = sum(process_job(job, factory) for job in jobs)
    if purge:
        stats = {}
        while True:
            with factory() as db:
                batch = sweep(db)
            for key, count in batch.items():
                stats[key] = stats.get(key, 0) + count
            if not any(batch.values()):
                break
    else:
        stats = {}
    return {"processed_batches": processed, "purge": stats}


def main():
    parser = argparse.ArgumentParser(description="Bounded privacy jobs and daily UTC purge")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--retry-marker")
    parser.add_argument("--retry-job")
    parser.add_argument("--init-authority", action="store_true")
    parser.add_argument("--reconcile-authority", action="store_true")
    args = parser.parse_args()
    if args.init_authority or args.reconcile_authority:
        with SessionLocal() as db:
            (initialise_authority if args.init_authority else reconcile_authority)(db)
        return
    if args.dry_run:
        with SessionLocal() as db:
            require_authority(db)
            print({"due_jobs": db.scalar(select(func.count()).select_from(PrivacyJob).where(
                PrivacyJob.state.in_(["queued", "retrying"]), PrivacyJob.next_attempt_at <= int(time.time()))),
                "configuration": policy.model_dump()})
        return
    if args.retry_marker:
        with SessionLocal() as db:
            print({"retry_job": retry_marker(db, args.retry_marker)})
        return
    if args.retry_job:
        with SessionLocal() as db:
            print({"retry_job": retry_job(db, args.retry_job)})
        return
    if args.once:
        print(run_once())
        return
    last_purge = None
    while True:
        now = datetime.now(timezone.utc)
        due = (now.hour, now.minute) >= (policy.maintenance_hour_utc, policy.maintenance_minute_utc)
        purge = due and last_purge != now.date()
        run_once(purge=purge)
        if purge:
            last_purge = now.date()
        current = datetime.now(timezone.utc)
        next_purge = current.replace(hour=policy.maintenance_hour_utc, minute=policy.maintenance_minute_utc, second=0, microsecond=0)
        if next_purge <= current:
            next_purge += timedelta(days=1)
        next_poll = (int(current.timestamp()) // policy.poll_seconds + 1) * policy.poll_seconds
        time.sleep(max(0, min(next_poll, next_purge.timestamp()) - current.timestamp()))


if __name__ == "__main__":
    main()
