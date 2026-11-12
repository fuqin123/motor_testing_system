"""日期回看：把前端选择的本地日期解析为 UTC 查询区间。"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.core.time import as_utc, local_day_bounds_utc, local_now, utcnow


@dataclass
class DateView:
    day: date
    is_today: bool
    day_start: datetime
    day_end: datetime
    as_of: datetime

    @property
    def date_text(self) -> str:
        return self.day.isoformat()


def resolve_date_view(value: str | None, now: datetime | None = None) -> DateView:
    current = as_utc(now or utcnow())
    assert current is not None
    today = local_now().date() if now is None else current.astimezone(local_now().tzinfo).date()
    if value:
        try:
            selected = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("日期格式应为 YYYY-MM-DD") from exc
        if selected > today:
            raise ValueError("不能查看未来日期")
    else:
        selected = today
    day_start, day_end = local_day_bounds_utc(selected)
    is_today = selected == today
    if is_today:
        as_of = current
    else:
        as_of = day_end - timedelta(microseconds=1)
    return DateView(
        day=selected,
        is_today=is_today,
        day_start=day_start,
        day_end=day_end,
        as_of=as_of,
    )
