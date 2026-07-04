from datetime import datetime, timedelta

from django.utils import timezone


def _add_one_month(value):
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)


def get_period_bounds(
    period: str, reference_date: datetime | None = None
) -> tuple[datetime, datetime]:
    if reference_date is None:
        reference_date = timezone.now()

    if timezone.is_naive(reference_date):
        reference_date = timezone.make_aware(reference_date)

    ref_date = timezone.localtime(reference_date).date()

    if period == "daily":
        start_date = ref_date
        end_date = ref_date + timedelta(days=1)
    elif period == "weekly":
        start_date = ref_date - timedelta(days=ref_date.weekday())
        end_date = start_date + timedelta(days=7)
    elif period == "monthly":
        start_date = ref_date.replace(day=1)
        end_date = _add_one_month(start_date)
    else:
        raise ValueError(f"Unknown period: {period}")

    start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end = timezone.make_aware(datetime.combine(end_date, datetime.min.time()))
    return start, end
