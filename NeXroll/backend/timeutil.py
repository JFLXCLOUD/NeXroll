"""The current UTC time without datetime.utcnow(), which Python 3.12 deprecated.

NeXroll keeps naive UTC datetimes everywhere (database columns, the values it
compares them with), so utcnow() returns the same naive value utcnow() did.
datetime.now(timezone.utc) on its own is timezone-aware, and comparing it with
a stored naive value raises TypeError.
"""
import datetime


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
