# -*- coding: utf-8 -*-
"""Tests for JC-25 deposit type sanity checks."""
import pandas as pd
import pytest
import sys, os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m10_sanity import (
    SanityWarning, check_deposit_type_match, check_unknown_rock_fraction,
    run_all_sanity_checks
)
from core.config import ProjectConfig


def _litho_df(code_counts):
    """Helper: build a litho dataframe with given code frequencies."""
    rows = []
    for code, count in code_counts.items():
        rows.extend([{'lcode': code}] * count)
    return pd.DataFrame(rows)


def test_sedex_with_sediment_host_passes():
    cfg = ProjectConfig()
    cfg.deposit_type = 'SEDEX Pb-Zn'
    df = _litho_df({1: 70, 4: 10, 3: 10, 2: 5, 5: 5})  # 80% host
    warnings = check_deposit_type_match(cfg, df)
    # Should produce no warnings
    assert all(w.severity == 'info' for w in warnings)


def test_sedex_with_volcanic_data_warns():
    cfg = ProjectConfig()
    cfg.deposit_type = 'SEDEX Pb-Zn'
    df = _litho_df({5: 70, 1: 10, 2: 10, 3: 10})  # 70% volcanic
    warnings = check_deposit_type_match(cfg, df)
    # Should warn about volcanic content
    assert len(warnings) > 0
    assert any('VMS' in w.message or 'volcanic' in w.message.lower() for w in warnings)


def test_vms_with_felsic_passes():
    cfg = ProjectConfig()
    cfg.deposit_type = 'VMS Cu-Zn'
    df = _litho_df({5: 50, 1: 20, 2: 10, 3: 15, 4: 5})  # 50% felsic
    warnings = check_deposit_type_match(cfg, df)
    assert all(w.severity != 'critical' for w in warnings)


def test_vms_with_sediment_warns():
    cfg = ProjectConfig()
    cfg.deposit_type = 'VMS Cu-Zn'
    df = _litho_df({1: 80, 4: 10, 3: 5, 5: 3, 2: 2})  # 90% sediment
    warnings = check_deposit_type_match(cfg, df)
    assert any(w.severity == 'warning' for w in warnings)


def test_porphyry_no_intrusive_warns():
    cfg = ProjectConfig()
    cfg.deposit_type = 'Porphyry Cu-Mo'
    df = _litho_df({1: 80, 5: 15, 4: 5})  # 0% intrusive
    warnings = check_deposit_type_match(cfg, df)
    assert any(w.severity == 'warning' for w in warnings)


def test_unknown_rock_warning():
    cfg = ProjectConfig()
    df = _litho_df({0: 30, 1: 70})  # 30% unknown
    warnings = check_unknown_rock_fraction(cfg, df)
    assert len(warnings) == 1
    assert 'unknown' in warnings[0].message.lower()


def test_low_unknown_no_warning():
    cfg = ProjectConfig()
    df = _litho_df({0: 5, 1: 95})  # only 5% unknown
    warnings = check_unknown_rock_fraction(cfg, df)
    assert len(warnings) == 0


def test_empty_df_no_crash():
    cfg = ProjectConfig()
    cfg.deposit_type = 'SEDEX Pb-Zn'
    warnings = run_all_sanity_checks(cfg, pd.DataFrame())
    assert warnings == []


def test_run_all_combines_checks():
    cfg = ProjectConfig()
    cfg.deposit_type = 'SEDEX Pb-Zn'
    # Data with both volcanic content AND high unknown rate
    df = _litho_df({0: 20, 5: 50, 1: 20, 2: 10})
    warnings = run_all_sanity_checks(cfg, df)
    # Should trigger both deposit-type and unknown-rock warnings
    assert len(warnings) >= 2


def test_warning_has_actions():
    cfg = ProjectConfig()
    cfg.deposit_type = 'VMS Cu-Zn'
    df = _litho_df({1: 100})  # 100% sediment, 0% felsic
    warnings = check_deposit_type_match(cfg, df)
    assert all(len(w.actions) > 0 for w in warnings)
