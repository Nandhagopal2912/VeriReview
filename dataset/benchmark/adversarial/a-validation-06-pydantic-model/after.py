from pydantic import BaseModel, Field


class ChargeRequest(BaseModel):
    amount: float = Field(gt=0)


def charge(gateway, card, amount):
    ChargeRequest(amount=amount)  # raises ValidationError unless amount > 0
    return gateway.charge(card, amount)
