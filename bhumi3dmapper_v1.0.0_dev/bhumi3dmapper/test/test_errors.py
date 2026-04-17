# -*- coding: utf-8 -*-
"""Tests for JC-27 plain-language error translation."""
import pytest
import sys, os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from core.errors import UserError, translate, format_for_display


def test_filenotfound_translated():
    exc_ref = None
    try:
        open('/nonexistent/path/file.csv', 'r')
    except FileNotFoundError as e:
        exc_ref = e
        ue = translate(e)
    assert 'Cannot find' in ue.message
    assert ue.suggestion and len(ue.suggestion) > 20
    assert ue.technical is exc_ref


def test_keyerror_suggests_remap():
    err = KeyError('XCOLLAR')
    ue = translate(err)
    assert 'XCOLLAR' in ue.message
    assert 'Remap' in ue.suggestion or 'rename' in ue.suggestion


def test_unicodedecodeerror_suggests_utf8():
    err = UnicodeDecodeError('ascii', b'\x80', 0, 1, 'bad byte')
    ue = translate(err)
    assert 'encoding' in ue.message.lower()
    assert 'UTF-8' in ue.suggestion or 'utf-8' in ue.suggestion.lower()


def test_valueerror_number_conversion():
    err = ValueError("could not convert string to float: 'N/A'")
    ue = translate(err)
    assert 'non-numeric' in ue.message.lower() or 'numeric' in ue.message.lower()


def test_permissionerror_suggests_close_excel():
    err = PermissionError(13, 'Permission denied', 'output.gpkg')
    ue = translate(err)
    assert 'Excel' in ue.suggestion or 'QGIS' in ue.suggestion


def test_memoryerror_suggests_smaller_grid():
    err = MemoryError()
    ue = translate(err)
    assert 'memory' in ue.message.lower()
    assert 'grid' in ue.suggestion.lower() or 'levels' in ue.suggestion.lower()


def test_user_error_passthrough():
    """Already-translated errors should pass through unchanged."""
    ue1 = UserError('Test', 'Do something', severity='warning')
    ue2 = translate(ue1)
    assert ue2 is ue1


def test_unknown_exception_has_fallback():
    class CustomError(Exception):
        pass
    err = CustomError("something odd")
    ue = translate(err)
    assert ue.message
    assert ue.suggestion
    assert ue.severity == 'critical'


def test_format_for_display_includes_message():
    ue = UserError('Bad file', 'Fix it', severity='error')
    out = format_for_display(ue)
    assert 'Bad file' in out
    assert 'Fix it' in out


def test_format_for_display_hides_technical_by_default():
    err = ValueError('raw error')
    ue = translate(err)
    out = format_for_display(ue)
    assert 'ValueError' not in out


def test_format_for_display_shows_technical_when_requested():
    err = ValueError('raw error')
    ue = translate(err)
    out = format_for_display(ue, include_technical=True)
    assert 'ValueError' in out or 'raw error' in out


def test_severity_levels():
    assert translate(FileNotFoundError(2, 'no such', 'x.csv')).severity == 'error'
    assert translate(MemoryError()).severity == 'critical'


def test_context_preserved():
    err = KeyError('BHID')
    ue = translate(err, context='loading collar.csv')
    assert ue.context == 'loading collar.csv'


def test_to_dict_has_all_fields():
    err = KeyError('ZN')
    ue = translate(err, context='test')
    d = ue.to_dict()
    assert 'message' in d
    assert 'suggestion' in d
    assert 'severity' in d
    assert 'context' in d
