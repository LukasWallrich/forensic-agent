"""GRIM test: can a mean of integer data with this n have the reported decimals?"""
from decimal import Decimal
from fractions import Fraction
from math import ceil


def _num(value):
    """Parse a reported number (kept as string) into a finite Decimal, else None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        d = Decimal(str(value).strip().replace("−", "-").replace(",", ""))
    except Exception:
        return None
    return d if d.is_finite() else None


def _result(status, detail, **computed):
    return {"status": status, "detail": detail, "computed": computed}


def check(claim: dict) -> dict:
    if not isinstance(claim, dict):
        return _result("insufficient", "Claim is not a JSON object.")
    mean, n = _num(claim.get("mean")), _num(claim.get("n"))
    items = _num(claim.get("items")) if claim.get("items") not in (None, "") else Decimal(1)
    if mean is None or n is None or items is None:
        return _result("insufficient", "Could not parse mean, n or items as numbers.")
    if n != n.to_integral_value() or items != items.to_integral_value() or n < 1 or items < 1:
        return _result("insufficient", "n and items must be positive whole numbers.")
    decimals = max(0, -mean.as_tuple().exponent)
    total = int(n) * int(items)
    if total >= 10 ** decimals:
        return _result("not_applicable",
                       f"GRIM has no power here: n x items = {total} is not below 10^{decimals}, "
                       f"so every mean with {decimals} decimal(s) is possible.",
                       decimals=decimals, total=total)
    # Sums k whose mean k/total lies in [mean - half unit, mean + half unit]; both ends are
    # included so that round-half-up and round-half-even are each accepted.
    half = Fraction(1, 2 * 10 ** decimals)
    target = Fraction(mean)
    low, high = (target - half) * total, (target + half) * total
    k = ceil(low)
    nearest = [round(Fraction(s, total).__float__(), decimals + 2)
               for s in (int(target * total), int(target * total) + (1 if target >= 0 else -1))]
    computed = dict(decimals=decimals, total=total, nearest_possible_means=sorted(nearest))
    if k <= high:
        return _result("pass", f"Mean {mean} is possible with n = {total}: a sum of {k} gives "
                               f"{float(Fraction(k, total)):.{decimals + 2}f}.", sum=k, **computed)
    return _result("fail", f"Mean {mean} is impossible for integer data with n = {total}; the nearest "
                           f"possible means are {nearest[0]} and {nearest[1]}.", **computed)
