from collections import defaultdict
from datetime import timezone


def my_group_by(iterable, keyfunc):
    """Because itertools.groupby is tricky to use

    The stdlib method requires sorting in advance, and returns iterators not
    lists, and those iterators get consumed as you try to use them, throwing
    everything off if you try to look at something more than once.
    """
    ret = defaultdict(list)
    for k in iterable:
        ret[keyfunc(k)].append(k)
    return dict(ret)


def timestamp_to_order(dt):
    """
    Convert a datetime object to a float in the format yyyymmdd.hhmmss

    Args:
        dt: A datetime object in UTC

    Returns:
        A float where the whole number portion is yyyymmdd and the decimal portion
        is the time in hhmmss format (e.g., 12:34:56 UTC = 0.123456)
    """
    if dt is None:
        return None

    # Ensure the datetime is in UTC
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)

    # Calculate the date portion (yyyymmdd)
    date_portion = dt.year * 10000 + dt.month * 100 + dt.day

    # Format time as hhmmss
    time_portion = dt.hour * 10000 + dt.minute * 100 + dt.second
    time_decimal = (
        time_portion / 1000000
    )  # Convert to decimal (e.g., 123456 -> 0.123456)

    # Combine the date portion and time decimal
    return date_portion + time_decimal
