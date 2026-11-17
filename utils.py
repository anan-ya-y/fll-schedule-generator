from __future__ import annotations

from datetime import datetime, time, timedelta


class TimeUtils:
    @staticmethod
    def add_times(start: time, minutes: int) -> time:
        return (datetime.combine(datetime.today(), start) + timedelta(minutes=minutes)).time()

    @staticmethod
    def subtract_times(later: time, earlier: time) -> int:
        delta = datetime.combine(datetime.today(), later) - datetime.combine(
            datetime.today(), earlier
        )
        return int(delta.total_seconds() // 60)

    @staticmethod
    def contains_overlap(intervals: list[tuple[time, int]]) -> bool:
        ordered = sorted(
            ((start, TimeUtils.add_times(start, duration)) for start, duration in intervals),
            key=lambda item: item[0],
        )
        return any(ordered[index][0] < ordered[index - 1][1] for index in range(1, len(ordered)))

