"""Recompute a p-value from its test statistic and df (statcheck-style), allowing for rounding."""
from decimal import Decimal

from scipy import stats

DF_NEEDED = {"t": 1, "F": 2, "chi2": 1, "z": 0, "r": 1}


def _num(value):
    """Parse a reported number (kept as string) into a finite Decimal, else None."""
    try:
        d = Decimal(str(value).strip().replace("−", "-").replace(",", ""))
    except Exception:
        return None
    return d if d.is_finite() and not isinstance(value, bool) else None


def _half_unit(d):
    """Half a unit of the last reported decimal place."""
    return float(Decimal(1).scaleb(min(d.as_tuple().exponent, 0))) / 2


def _p(test, x, df1, df2):
    """Two-tailed p (upper tail for F and chi2) for a non-negative statistic x."""
    if test == "r":
        x = min(x, 1 - 1e-12)
        test, x = "t", x * (df1 / (1 - x * x)) ** 0.5
    if test in ("z", "t"):
        return float(2 * (stats.norm.sf(x) if test == "z" else stats.t.sf(x, df1)))
    return float(stats.f.sf(x, df1, df2) if test == "F" else stats.chi2.sf(x, df1))


def check(claim: dict) -> dict:
    def out(status, detail, **computed):
        return {"status": status, "detail": detail, "computed": computed}
    if not isinstance(claim, dict):
        return out("insufficient", "Claim is not a JSON object.")
    test = str(claim.get("test", "")).strip()
    test = "F" if test == "f" else test
    comp = str(claim.get("p_comparator") or "=").strip()
    if test not in DF_NEEDED or comp not in ("=", "<", ">"):
        return out("insufficient", f"Unsupported test '{test}' or p comparator '{comp}'.")
    stat, rp = _num(claim.get("statistic")), _num(claim.get("p"))
    dfs = [_num(claim.get(k)) for k in ("df1", "df2")][:DF_NEEDED[test]]
    if stat is None or rp is None or not 0 <= rp <= 1 or any(d is None or d <= 0 for d in dfs):
        return out("insufficient", "Could not parse the statistic, p-value or required degrees of freedom.")
    if (test in ("F", "chi2") and stat < 0) or (test == "r" and abs(stat) > 1):
        return out("insufficient", f"A {test} statistic of {stat} is outside its possible range.")
    df1, df2 = [float(d) for d in dfs] + [None] * (2 - len(dfs))
    two_sided = test in ("t", "z", "r")
    tails = 0.5 if claim.get("one_tailed") is True and two_sided else 1.0
    x, half, r, p_half = abs(float(stat)), _half_unit(stat), float(rp), _half_unit(rp)
    p_mid, p_hi, p_lo = (_p(test, v, df1, df2) * tails for v in (x, max(x - half, 0.0), x + half))

    def consistent(k=1.0):  # does the reported p fit the recomputed range (scaled by k)?
        if comp == "=":
            return p_lo * k <= r + p_half + 1e-12 and p_hi * k >= r - p_half - 1e-12
        return p_lo * k < r if comp == "<" else p_hi * k > r
    ok = consistent()
    reported_sig = {"=": r < .05, "<": True if r <= .05 else None, ">": False if r >= .05 else None}[comp]
    computed_sig = True if p_hi < .05 else False if p_lo >= .05 else None
    decision_error = not ok and None not in (reported_sig, computed_sig) and reported_sig != computed_sig
    computed = dict(p=round(p_mid, 6), p_min=round(p_lo, 6), p_max=round(p_hi, 6), decision_error=decision_error)
    rng = f"recomputed p = {p_mid:.4f} (range {p_lo:.4f}-{p_hi:.4f} given rounding of the statistic)"
    if ok:
        return out("pass", f"Reported p {comp} {rp} is consistent: {rng}.", **computed)
    if two_sided and tails == 1.0:
        computed["consistent_if_one_tailed"] = consistent(0.5)
    kind = "a decision error, as the discrepancy crosses the .05 threshold" if decision_error \
        else "the discrepancy does not cross the .05 threshold"
    return out("fail", f"Reported p {comp} {rp} is inconsistent: {rng}; {kind}.", **computed)
