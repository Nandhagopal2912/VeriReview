def book(calendar, start, end):
    if start is None or end is None:
        raise ValueError("start and end are required")
    calendar.add(start, end)
