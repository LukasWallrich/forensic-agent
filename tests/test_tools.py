"""Tests for the deterministic tools, loaded the same way the core loads them."""
import pytest

from forensic_agent.loader import load_tools
from forensic_agent.models import TOOL_STATUSES

TOOLS = load_tools()


def run(tool, **claim):
    result = TOOLS[tool].check(claim)
    assert set(result) == {"status", "detail", "computed"}
    assert result["status"] in TOOL_STATUSES
    assert isinstance(result["detail"], str) and result["detail"]
    assert isinstance(result["computed"], dict)
    return result


def test_tools_are_discovered_with_metadata():
    assert {"grim", "p_recompute", "percent_check"} <= set(TOOLS)
    assert TOOLS["grim"].fields == ["mean", "n"]
    assert TOOLS["p_recompute"].fields == ["test", "statistic", "p"]
    assert TOOLS["percent_check"].fields == ["count", "total", "percent"]
    for tool in TOOLS.values():
        assert tool.claim_type == tool.name
        assert '"quote"' in tool.doc and len(tool.doc.splitlines()) <= 15


@pytest.mark.parametrize("tool", ["grim", "p_recompute", "percent_check"])
@pytest.mark.parametrize("claim", [{}, None, "text", {"mean": None, "n": [], "test": 3, "p": {}, "count": True}])
def test_bad_input_never_raises(tool, claim):
    assert TOOLS[tool].check(claim)["status"] == "insufficient"


# ---------------------------------------------------------------- grim
def test_grim_pass():
    assert run("grim", mean="5.18", n="28")["status"] == "pass"  # 145 / 28 = 5.179


def test_grim_classic_fail():
    result = run("grim", mean="5.19", n="28")
    assert result["status"] == "fail"
    assert result["computed"]["nearest_possible_means"] == [5.1786, 5.2143]


def test_grim_not_applicable_without_power():
    assert run("grim", mean="5.19", n="100")["status"] == "not_applicable"
    assert run("grim", mean="3.5", n="25")["status"] == "not_applicable"
    assert run("grim", mean="5.19", n="28", items="4")["status"] == "not_applicable"  # 112 >= 100


def test_grim_items_change_granularity():
    assert run("grim", mean="2.45", n="10")["status"] == "fail"
    assert run("grim", mean="2.45", n="10", items="2")["status"] == "pass"  # 49 / 20


def test_grim_rounding_boundary_accepts_half_up_and_half_even():
    # 25 / 8 = 3.125 exactly: 3.13 (half-up) and 3.12 (half-even) are both legitimate
    assert run("grim", mean="3.13", n="8")["status"] == "pass"
    assert run("grim", mean="3.12", n="8")["status"] == "pass"
    assert run("grim", mean="3.14", n="8")["status"] == "fail"


def test_grim_trailing_zero_and_numeric_input():
    assert run("grim", mean="3.50", n="28")["status"] == "pass"  # 98 / 28
    assert run("grim", mean=5.19, n=28)["status"] == "fail"  # tolerates non-string input


def test_grim_insufficient():
    assert run("grim", mean="about 5", n="28")["status"] == "insufficient"
    assert run("grim", mean="5.19", n="28.5")["status"] == "insufficient"
    assert run("grim", mean="5.19", n="0")["status"] == "insufficient"


# ---------------------------------------------------------------- p_recompute
def test_p_pass_all_test_types():
    assert run("p_recompute", test="t", statistic="2.20", df1="28", p=".036")["status"] == "pass"
    assert run("p_recompute", test="t", statistic="−2.20", df1="28", p=".036")["status"] == "pass"
    assert run("p_recompute", test="F", statistic="4.11", df1="2", df2="57", p=".05",
               p_comparator="<")["status"] == "pass"
    assert run("p_recompute", test="chi2", statistic="3.84", df1="1", p=".05")["status"] == "pass"
    assert run("p_recompute", test="z", statistic="1.96", p=".05")["status"] == "pass"
    assert run("p_recompute", test="r", statistic=".31", df1="48", p=".03")["status"] == "pass"
    assert run("p_recompute", test="t", statistic="5.12", df1="40", p=".001", p_comparator="<")["status"] == "pass"


def test_p_fail_with_decision_error():
    result = run("p_recompute", test="t", statistic="1.70", df1="28", p=".04")  # true p = .100
    assert result["status"] == "fail"
    assert result["computed"]["decision_error"] is True
    assert "decision error" in result["detail"]
    assert result["computed"]["p"] == pytest.approx(0.1002, abs=1e-3)


def test_p_fail_without_decision_error():
    result = run("p_recompute", test="t", statistic="2.20", df1="28", p=".01")  # true p = .036
    assert result["status"] == "fail"
    assert result["computed"]["decision_error"] is False
    assert "does not cross" in result["detail"]


def test_p_comparator_fail():
    result = run("p_recompute", test="F", statistic="2.50", df1="2", df2="57", p=".05", p_comparator="<")
    assert result["status"] == "fail" and result["computed"]["decision_error"] is True  # true p = .091
    assert run("p_recompute", test="z", statistic="2.50", p=".05", p_comparator=">")["status"] == "fail"


def test_p_rounding_boundary_of_statistic_and_p():
    # t(28) = 2.05 -> p = .0498, but t in [2.045, 2.055] gives p in [.0493, .0503]
    result = run("p_recompute", test="t", statistic="2.05", df1="28", p=".05", p_comparator=">")
    assert result["status"] == "pass" and result["computed"]["decision_error"] is False
    assert result["computed"]["p_min"] < 0.05 < result["computed"]["p_max"]
    # p = .0362 rounds to .04 at two decimals and to .036 at three, never to .03
    assert run("p_recompute", test="t", statistic="2.20", df1="28", p=".04")["status"] == "pass"
    assert run("p_recompute", test="t", statistic="2.20", df1="28", p=".03")["status"] == "fail"
    # a coarsely reported statistic widens the range: t = 2.2 covers 2.15-2.25 (p = .040-.033)
    assert run("p_recompute", test="t", statistic="2.2", df1="28", p=".039")["status"] == "pass"
    assert run("p_recompute", test="t", statistic="2.20", df1="28", p=".039")["status"] == "fail"


def test_p_one_tailed():
    claim = dict(test="t", statistic="1.80", df1="28", p=".041")  # two-tailed p = .083
    two = run("p_recompute", **claim)
    assert two["status"] == "fail" and two["computed"]["consistent_if_one_tailed"] is True
    assert run("p_recompute", one_tailed=True, **claim)["status"] == "pass"


def test_p_insufficient():
    assert run("p_recompute", test="t", statistic="2.20", p=".036")["status"] == "insufficient"  # no df
    assert run("p_recompute", test="F", statistic="4.11", df1="2", p=".02")["status"] == "insufficient"
    assert run("p_recompute", test="t", statistic="n/a", df1="28", p=".036")["status"] == "insufficient"
    assert run("p_recompute", test="U", statistic="2.20", df1="28", p=".036")["status"] == "insufficient"
    assert run("p_recompute", test="t", statistic="2.20", df1="28", p="1.5")["status"] == "insufficient"
    assert run("p_recompute", test="r", statistic="1.31", df1="48", p=".03")["status"] == "insufficient"


# ---------------------------------------------------------------- percent_check
def test_percent_pass():
    result = run("percent_check", count="23", total="61", percent="37.7")
    assert result["status"] == "pass"
    assert result["computed"]["percent"] == pytest.approx(37.705)
    assert run("percent_check", count="23", total="61", percent="38%")["status"] == "pass"
    assert run("percent_check", count="1,234", total="2,468", percent="50.0")["status"] == "pass"


def test_percent_fail():
    assert run("percent_check", count="23", total="61", percent="37.1")["status"] == "fail"
    assert run("percent_check", count="23", total="61", percent="37.71")["status"] == "fail"  # 37.7049 -> 37.70


def test_percent_rounding_boundary_accepts_half_up_and_half_even():
    # 1 / 8 = 12.5 % exactly
    assert run("percent_check", count="1", total="8", percent="13")["status"] == "pass"
    assert run("percent_check", count="1", total="8", percent="12")["status"] == "pass"
    assert run("percent_check", count="1", total="8", percent="14")["status"] == "fail"
    assert run("percent_check", count="1", total="3", percent="33.3")["status"] == "pass"
    assert run("percent_check", count="1", total="3", percent="33.4")["status"] == "fail"


def test_percent_insufficient():
    assert run("percent_check", count="23", total="0", percent="37.7")["status"] == "insufficient"
    assert run("percent_check", count="61", total="23", percent="37.7")["status"] == "insufficient"
    assert run("percent_check", count="some", total="61", percent="37.7")["status"] == "insufficient"
    assert run("percent_check", count="2.5", total="61", percent="4.1")["status"] == "insufficient"
