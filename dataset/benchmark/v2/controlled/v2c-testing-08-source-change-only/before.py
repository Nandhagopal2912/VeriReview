def discount(coupon, today):
    if coupon.expires < today:
        return 0
    return coupon.percent
