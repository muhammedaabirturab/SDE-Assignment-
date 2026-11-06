"""Exact money helpers.

All money is stored and calculated as an integer number of paise
(1 INR = 100 paise). ``Decimal`` is only used to read rupee amounts from
requests without ever touching binary floating point.
"""

from collections.abc import Iterable
from decimal import Decimal

PAISE_PER_RUPEE = 100


def rupees_to_paise(rupees: Decimal) -> int:
    """Convert a rupee ``Decimal`` with at most 2 decimal places to paise."""
    paise = rupees * PAISE_PER_RUPEE
    if paise != paise.to_integral_value():
        raise ValueError("Amount cannot have more than 2 decimal places")
    return int(paise)


def paise_to_json_number(paise: int) -> int | float:
    """Rupee value of ``paise`` as a JSON number (``400`` or ``400.5``).

    This is the *only* place a float can appear and it happens at the very
    end of a request, after every calculation was done in integer paise.
    Values with at most two decimals round-trip exactly through JSON.
    """
    if paise % PAISE_PER_RUPEE == 0:
        return paise // PAISE_PER_RUPEE
    return float(Decimal(paise) / PAISE_PER_RUPEE)


def split_equally(total_paise: int, user_ids: Iterable[int]) -> dict[int, int]:
    """Split ``total_paise`` equally between ``user_ids``, never losing a paisa.

    Everyone gets ``total // n``. The ``total % n`` leftover paise are handed
    out one each to the participants with the lowest user ids, so the result
    is deterministic and always sums exactly to ``total_paise``.
    """
    ordered = sorted(set(user_ids))
    if not ordered:
        raise ValueError("At least one participant is required")
    base, remainder = divmod(total_paise, len(ordered))
    return {
        user_id: base + (1 if index < remainder else 0)
        for index, user_id in enumerate(ordered)
    }
