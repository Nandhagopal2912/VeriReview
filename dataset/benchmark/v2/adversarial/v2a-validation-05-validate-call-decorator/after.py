from typing import Annotated

from pydantic import Field, validate_call


@validate_call
def set_limit(account, limit: Annotated[int, Field(ge=0)]):
    account.limit = limit
