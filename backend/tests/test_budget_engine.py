"""Unit tests for the section 5 formulas and alert thresholds."""

from decimal import Decimal as D

from app.budget import CostLine, evaluate_alert, summarize
from app.models import AlertLevel
from app.models import CostType as T


def lines(*pairs):
    return [CostLine(t, D(str(a)), p) for t, a, *rest in pairs for p in (rest[0] if rest else None,)]


def test_formulas_match_spec():
    s = summarize(
        D("100000"),
        lines(
            (T.invoice, 10000),
            (T.labor, 15000),
            (T.material, 20000),  # E_actual = 45,000
            (T.purchase_order, 8000),
            (T.unbilled_subcontract, 7000),  # C_committed = 15,000
            (T.remaining_estimate, 30000),  # remaining = 30,000
        ),
    )
    assert s.actual_total == D("45000.00")
    assert s.committed_total == D("15000.00")
    assert s.projected_total == D("90000.00")  # P_total = 45k + 15k + 30k
    assert s.cost_variance == D("10000.00")  # CV = 100k - 90k
    assert s.burn_rate_pct == D("60.00")  # (45k + 15k) / 100k
    assert s.remaining_budget == D("40000.00")
    assert s.alert_level is AlertLevel.none


def test_warning_at_exactly_85_percent():
    s = summarize(D("100000"), lines((T.material, 85000)))
    assert s.burn_rate_pct == D("85.00")
    assert s.alert_level is AlertLevel.warning


def test_just_below_warning():
    s = summarize(D("100000"), lines((T.material, "84999.99")))
    assert s.alert_level is AlertLevel.none


def test_critical_at_exactly_100_percent():
    s = summarize(D("100000"), lines((T.labor, 60000), (T.purchase_order, 40000)))
    assert s.burn_rate_pct == D("100.00")
    assert s.cost_variance == D("0.00")
    assert s.alert_level is AlertLevel.critical


def test_critical_when_cv_negative_even_with_low_burn():
    # Only 50% burned, but the remaining estimate pushes projection over budget.
    s = summarize(D("100000"), lines((T.material, 50000), (T.remaining_estimate, 50000.01)))
    assert s.burn_rate_pct == D("50.00")
    assert s.cost_variance == D("-0.01")
    assert s.alert_level is AlertLevel.critical
    assert any("CV < 0" in r for r in s.alert_reasons)


def test_remaining_estimate_not_in_burn_rate():
    s = summarize(D("1000"), lines((T.remaining_estimate, 900)))
    assert s.burn_rate_pct == D("0.00")
    assert s.projected_total == D("900.00")


def test_no_budget():
    s = summarize(D("0"), [])
    assert s.burn_rate_pct is None
    assert s.alert_level is AlertLevel.none
    s2 = summarize(D("0"), lines((T.labor, 100)))
    assert s2.cost_variance == D("-100.00")
    assert s2.alert_level is AlertLevel.critical


def test_by_phase_rollup_excludes_estimates():
    s = summarize(
        D("50000"),
        lines(
            (T.material, 1000, "slab"), (T.labor, 500, "slab"), (T.invoice, 200), (T.remaining_estimate, 9999, "slab")
        ),
    )
    assert s.by_phase == {"slab": D("1500.00"), "unassigned": D("200.00")}


def test_custom_thresholds():
    level, _ = evaluate_alert(D("80"), D("1"), warning_pct=75, critical_pct=95)
    assert level is AlertLevel.warning


def test_rounding_to_cents():
    s = summarize(D("3"), lines((T.labor, 1)))
    assert s.burn_rate_pct == D("33.33")
