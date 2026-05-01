"""主垂直切片（排产→物料→入库→库存）L2 对账扩展字段。

与 ``docs/handbook-gap-and-industrialization.md`` 技能成熟度 **L2** 对齐：
输出中带可核对粒度、台账提示与（必要时）异常码 / 人工兜底文案。
"""

from __future__ import annotations

from typing import Any


def l2_reconcile_block(
    grain: str,
    keys: dict[str, Any],
    basis_qty_field: str,
    ledger_hint: str,
) -> dict[str, Any]:
    """嵌套写入各 Skill 的 ``summary[\"l2_reconcile\"]``。"""
    return {
        "grain": grain,
        "keys": keys,
        "basis_qty_field": basis_qty_field,
        "ledger_hint": ledger_hint,
    }
