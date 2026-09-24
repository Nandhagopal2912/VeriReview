def apply_markup(price, percent):
    if not 0 <= percent <= 100:
        raise ValueError(f"percent must be within 0..100, got {percent}")
    return price * (1 + percent / 100)
