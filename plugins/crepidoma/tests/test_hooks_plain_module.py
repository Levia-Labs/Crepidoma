"""hooks.py is a plain module: patching a name there does not reach the split hooks_* parts."""

import types

import hooks


def test_hooks_is_a_plain_module():
    assert type(hooks) is types.ModuleType
