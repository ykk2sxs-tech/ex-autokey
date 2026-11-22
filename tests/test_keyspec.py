import pytest

from exautokey.keyspec import KeyPress, KeySpecError, TypeText, Wait, parse_keys


def test_basic_keys():
    assert parse_keys("{ENTER}") == [KeyPress("ENTER")]
    assert parse_keys("{tab 3}") == [KeyPress("TAB", (), 3)]
    assert parse_keys("{Esc}{DEL}{BS}") == [KeyPress("ESC"), KeyPress("DELETE"), KeyPress("BACKSPACE")]
    assert parse_keys("") == []
    assert parse_keys(None) == []


def test_modifiers():
    assert parse_keys("^s") == [KeyPress("S", ("CTRL",))]
    assert parse_keys("%{F4}") == [KeyPress("F4", ("ALT",))]
    assert parse_keys("+{TAB}") == [KeyPress("TAB", ("SHIFT",))]
    assert parse_keys("+^a") == [KeyPress("A", ("CTRL", "SHIFT"))]


def test_text_and_literals():
    assert parse_keys("ab{+}c") == [TypeText("ab+c")]
    assert parse_keys("{{}x{}}") == [TypeText("{x}")]
    assert parse_keys("ก{ENTER}ข") == [TypeText("ก"), KeyPress("ENTER"), TypeText("ข")]


def test_wait():
    assert parse_keys("{ENTER}{WAIT 500}{ENTER}") == [KeyPress("ENTER"), Wait(500), KeyPress("ENTER")]


@pytest.mark.parametrize("spec", ["{ENTR}", "{ENTER", "^", "{WAIT}", "{TAB x}", "{TAB 0}", "^^s", "^{WAIT 5}", "^ก", "{TAB 99}"])
def test_errors(spec):
    with pytest.raises(KeySpecError):
        parse_keys(spec)
