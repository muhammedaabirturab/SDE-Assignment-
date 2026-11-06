"""Types shared by the request / response schemas."""

from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer, StringConstraints, WithJsonSchema

from app.utils.money import paise_to_json_number

# Incoming rupee amount: > 0, at most 2 decimal places, bounded so the paise
# value comfortably fits a BIGINT. Parsed as Decimal, never float.
RupeesInput = Annotated[
    Decimal,
    Field(gt=0, max_digits=12, decimal_places=2, examples=[1200]),
]

# Outgoing money: the field holds integer paise and is rendered as a rupee
# JSON number, e.g. 40000 -> 400 and 12345 -> 123.45.
Rupees = Annotated[
    int,
    PlainSerializer(paise_to_json_number, return_type=float | int),
    WithJsonSchema({"type": "number", "description": "Amount in rupees (max 2 decimals)"}),
]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
