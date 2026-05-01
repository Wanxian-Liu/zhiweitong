"""财务中心 Skills (Phase 2).

Package exports are lazy so :func:`importlib.util.find_spec` does not load skill
modules before coverage tracing starts (see ``core.sandbox.run_sandbox``).
"""

from __future__ import annotations

from typing import Any

__all__ = ["PayableReconciliationSkill", "ReceivableReconciliationSkill"]


def __getattr__(name: str) -> Any:
    if name == "ReceivableReconciliationSkill":
        from skills.finance_center.receivable_reconciliation import ReceivableReconciliationSkill

        return ReceivableReconciliationSkill
    if name == "PayableReconciliationSkill":
        from skills.finance_center.payable_reconciliation import PayableReconciliationSkill

        return PayableReconciliationSkill
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
