"""Patch a hooks name where the split hooks_* modules read it."""

import hooks_bash
import hooks_budget
import hooks_common
import hooks_pre_tool
import hooks_stop

HOLDERS = {
    "ROOT": (hooks_common, hooks_budget, hooks_bash, hooks_pre_tool, hooks_stop),
    "opted_in": (hooks_common, hooks_budget, hooks_stop),
    "usage_reading": (hooks_budget, hooks_stop),
}


def patch_shared(monkeypatch, name: str, value: object) -> None:
    """Set a name every module that imported it holds."""
    for module in HOLDERS[name]:
        monkeypatch.setattr(module, name, value)
