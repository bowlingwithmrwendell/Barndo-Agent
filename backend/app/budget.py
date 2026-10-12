"""Budget calculation & variance alert engine (spec section 5).

    E_actual    = sum(invoices) + sum(labor) + sum(materials)
    C_committed = outstanding purchase orders + unbilled subcontracts
    P_total     = E_actual + C_committed + remaining estimated costs
    CV          = B_total - P_total
    BR%         = (E_actual + C_committed) / B_total * 100

    Warning  : BR% >= 85
    Critical : BR% >= 100  or  CV < 0

This module is pure (no database), so it can be unit tested directly and
ported 1:1 to Kotlin for the app's offline calculations.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.models import ACTUAL_TYPES, COMMITTED_TYPES, AlertLevel, CostType

CENT = Decimal("0.01")


def _money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CostLine:
    cost_type: CostType
    amount: Decimal
    phase: str | None = None


@dataclass
class BudgetSummary:
    budget_total: Decimal
    actual_invoices: Decimal
    actual_labor: Decimal
    actual_materials: Decimal
    actual_total: Decimal  # E_actual
    committed_purchase_orders: Decimal
    committed_unbilled_subcontracts: Decimal
    committed_total: Decimal  # C_committed
    remaining_estimated: Decimal
    projected_total: Decimal  # P_total
    cost_variance: Decimal  # CV
    burn_rate_pct: Decimal | None  # BR% (None when no budget set)
    remaining_budget: Decimal  # B_total - (E_actual + C_committed)
    alert_level: AlertLevel
    alert_reasons: list[str] = field(default_factory=list)
    by_phase: dict[str, Decimal] = field(default_factory=dict)


def evaluate_alert(
    burn_rate_pct: Decimal | None,
    cost_variance: Decimal,
    warning_pct: float = 85.0,
    critical_pct: float = 100.0,
) -> tuple[AlertLevel, list[str]]:
    reasons: list[str] = []
    level = AlertLevel.none
    warn, crit = Decimal(str(warning_pct)), Decimal(str(critical_pct))

    if burn_rate_pct is not None and burn_rate_pct >= crit:
        level = AlertLevel.critical
        reasons.append(f"Burn rate {burn_rate_pct:.2f}% is at or above {crit}% of budget")
    if cost_variance < 0:
        level = AlertLevel.critical
        reasons.append(f"Projected total exceeds budget by ${-cost_variance:,.2f} (CV < 0)")
    if level is AlertLevel.none and burn_rate_pct is not None and burn_rate_pct >= warn:
        level = AlertLevel.warning
        reasons.append(f"Burn rate {burn_rate_pct:.2f}% is at or above {warn}% of budget")
    return level, reasons


def summarize(
    budget_total: Decimal,
    lines: Iterable[CostLine],
    warning_pct: float = 85.0,
    critical_pct: float = 100.0,
) -> BudgetSummary:
    sums: dict[CostType, Decimal] = {t: Decimal("0") for t in CostType}
    by_phase: dict[str, Decimal] = {}

    for line in lines:
        amt = Decimal(line.amount)
        sums[line.cost_type] += amt
        if line.cost_type in ACTUAL_TYPES or line.cost_type in COMMITTED_TYPES:
            key = line.phase or "unassigned"
            by_phase[key] = by_phase.get(key, Decimal("0")) + amt

    b_total = Decimal(budget_total)
    e_actual = sum((sums[t] for t in ACTUAL_TYPES), Decimal("0"))
    c_committed = sum((sums[t] for t in COMMITTED_TYPES), Decimal("0"))
    remaining = sums[CostType.remaining_estimate]
    p_total = e_actual + c_committed + remaining
    cv = b_total - p_total

    burn_exact = None
    if b_total > 0:
        burn_exact = (e_actual + c_committed) / b_total * 100
    burn = None if burn_exact is None else burn_exact.quantize(CENT, rounding=ROUND_HALF_UP)

    # Thresholds are checked against the exact ratio; rounding is for display only,
    # so 84.999% never trips the 85% warning.
    level, reasons = evaluate_alert(burn_exact, cv, warning_pct, critical_pct)
    if b_total <= 0:
        reasons.append("No budget set for this project; burn rate cannot be calculated")

    return BudgetSummary(
        budget_total=_money(b_total),
        actual_invoices=_money(sums[CostType.invoice]),
        actual_labor=_money(sums[CostType.labor]),
        actual_materials=_money(sums[CostType.material]),
        actual_total=_money(e_actual),
        committed_purchase_orders=_money(sums[CostType.purchase_order]),
        committed_unbilled_subcontracts=_money(sums[CostType.unbilled_subcontract]),
        committed_total=_money(c_committed),
        remaining_estimated=_money(remaining),
        projected_total=_money(p_total),
        cost_variance=_money(cv),
        burn_rate_pct=burn,
        remaining_budget=_money(b_total - e_actual - c_committed),
        alert_level=level,
        alert_reasons=reasons,
        by_phase={k: _money(v) for k, v in sorted(by_phase.items())},
    )
