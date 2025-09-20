import math


def test_compute_initial_bracket_long():
    from trader.risk_manager import compute_initial_bracket

    entry = 100.0
    atr = 2.0
    k_sl = 2.0
    rr = 1.5

    sl, tp = compute_initial_bracket(entry=entry, atr=atr, side="long", k_sl=k_sl, rr=rr)

    assert math.isclose(sl, 96.0, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(tp, 106.0, rel_tol=0, abs_tol=1e-9)


def test_compute_initial_bracket_short():
    from trader.risk_manager import compute_initial_bracket

    entry = 100.0
    atr = 2.0
    k_sl = 2.0
    rr = 1.5

    sl, tp = compute_initial_bracket(entry=entry, atr=atr, side="short", k_sl=k_sl, rr=rr)

    assert math.isclose(sl, 104.0, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(tp, 94.0, rel_tol=0, abs_tol=1e-9)


def test_compute_initial_bracket_invalid_side():
    from trader.risk_manager import compute_initial_bracket

    try:
        compute_initial_bracket(entry=100.0, atr=2.0, side="invalid", k_sl=2.0, rr=1.5)
    except ValueError as e:
        assert "side" in str(e)
    else:
        assert False, "Expected ValueError for invalid side"


