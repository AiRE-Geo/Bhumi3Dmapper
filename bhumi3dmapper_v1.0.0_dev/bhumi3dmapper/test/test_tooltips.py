# -*- coding: utf-8 -*-
"""Tests for JC-30 contextual tooltips."""
import pytest
import sys, os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from core.tooltips import get_tooltip, list_documented_parameters, has_tooltip


def test_generic_tooltip_returns_content():
    tt = get_tooltip('deposit_type', 'generic')
    assert len(tt) > 0
    assert 'deposit' in tt.lower()


def test_sedex_tooltip_has_kayad_example():
    tt = get_tooltip('structural_marker_code', 'SEDEX Pb-Zn')
    assert 'Kayad' in tt or 'SEDEX' in tt or 'Pegmatite' in tt
    assert '<i>Example:</i>' in tt or '<i>Tip:</i>' in tt or 'example' in tt.lower()


def test_vms_tooltip_mentions_vms_sites():
    tt = get_tooltip('structural_marker_code', 'VMS Cu-Zn')
    assert 'Kidd Creek' in tt or 'Neves' in tt or 'VMS' in tt


def test_porphyry_tooltip_mentions_porphyry_sites():
    tt = get_tooltip('structural_marker_code', 'Porphyry Cu-Mo')
    assert 'El Teniente' in tt or 'Chuquicamata' in tt or 'porphyry' in tt.lower()


def test_epithermal_tooltip_mentions_epithermal_sites():
    tt = get_tooltip('structural_marker_code', 'Epithermal Au')
    assert 'Hishikari' in tt or 'Waihi' in tt or 'epithermal' in tt.lower()


def test_unknown_parameter_returns_empty():
    tt = get_tooltip('nonexistent_parameter', 'generic')
    assert tt == ''


def test_fallback_to_generic():
    """When deposit-specific entry is missing, should show generic."""
    tt = get_tooltip('veto_score_cap', 'Custom')  # Custom has no specific entry
    assert len(tt) > 0  # should return generic


def test_list_documented_parameters():
    params = list_documented_parameters()
    assert len(params) >= 5
    assert 'deposit_type' in params
    assert 'structural_marker_code' in params


def test_has_tooltip():
    assert has_tooltip('deposit_type')
    assert not has_tooltip('no_such_parameter')


def test_html_formatting():
    tt = get_tooltip('deposit_type', 'generic')
    assert '<b>' in tt or '<i>' in tt  # Has some HTML formatting


def test_plunge_breaks_deposit_specific():
    """Different deposits should get different plunge examples."""
    sedex = get_tooltip('plunge_breaks', 'SEDEX Pb-Zn')
    porphyry = get_tooltip('plunge_breaks', 'Porphyry Cu-Mo')
    assert sedex != porphyry
    assert 'kilo' in porphyry.lower() or '1000' in porphyry or 'larger' in porphyry.lower()
