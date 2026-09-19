"""Check that count / total * 100 matches the reported percentage at its reported precision."""
from decimal import Decimal
from fractions import Fraction


def _num(value):
    """Parse a reported number (kept as string) into a finite Decimal, else None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        d = Decimal(str(value).strip().rstrip("%").strip().replace("−", "-").replace(",", ""))
    except Exception:
        return None
    return d if d.is_finite() else None


def _result(status, detail, **computed):
    return {"status": status, "detail": detail, "computed": computed}


def check(claim: dict) -> dict:
    if not isinstance(claim, dict):
        return _result("insufficient", "Claim is not a JSON object.")
    count, total, percent = (_num(claim.get(k)) for k in ("count", "total", "percent"))
    if count is None or total is None or percent is None:
        return _result("insufficient", "Could not parse count, total or percent as numbers.")
    if count != count.to_integral_value() or total != total.to_integral_value():
        return _result("insufficient", "Count and total must be whole numbers.")
    if total <= 0 or count < 0 or count > total:
        return _result("insufficient", f"Count {count} of total {total} is not a valid proportion; "
                                       "the claim was probably mis-extracted.")
    decimals = max(0, -percent.as_tuple().exponent)
    exact = Fraction(int(count), int(total)) * 100
    # Inclusive half-unit tolerance accepts both round-half-up and round-half-even.
    ok = abs(exact - Fraction(percent)) <= Fraction(1, 2 * 10 ** decimals)
    shown = f"{float(exact):.{decimals + 2}f}"
    computed = dict(percent=float(shown), decimals=decimals)
    if ok:
        return _result("pass", f"{count}/{total} = {shown}%, consistent with the reported {percent}%.", **computed)
    return _result("fail", f"{count}/{total} = {shown}%, which does not round to the reported {percent}%.",
                   **computed)
