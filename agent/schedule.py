"""Daily storage collection uses explicit WIB (UTC+7), independent of host timezone."""
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7), name='WIB')

def next_storage_run(timestamp: float) -> float:
    current = datetime.fromtimestamp(timestamp, WIB)
    target = current.replace(hour=16, minute=0, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return target.timestamp()

class StorageSchedule:
    def __init__(self, started_at: float):
        self.next_due = started_at  # Always collect once when the agent starts.

    def is_due(self, timestamp: float) -> bool:
        return timestamp >= self.next_due

    def mark_attempt(self, timestamp: float) -> None:
        # Also advance after failure to avoid repeatedly spawning PowerShell.
        self.next_due = next_storage_run(timestamp)
