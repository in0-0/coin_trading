import math

from trader.position_sizer import kelly_position_size
from trader.risk_manager import compute_initial_bracket


def test_kelly_position_size_monotonic_and_clamped():
    cap = 1000.0
    # base
    a = kelly_position_size(capital=cap, win_rate=0.5, avg_win=1.0, avg_loss=1.0, score=0.2, max_score=1.0, f_max=0.2, pos_min=0.0, pos_max=0.2)
    b = kelly_position_size(capital=cap, win_rate=0.5, avg_win=1.0, avg_loss=1.0, score=0.6, max_score=1.0, f_max=0.2, pos_min=0.0, pos_max=0.2)
    assert b >= a
    # clamped by pos_max
    c = kelly_position_size(capital=cap, win_rate=0.8, avg_win=2.0, avg_loss=1.0, score=1.0, max_score=1.0, f_max=0.5, pos_min=0.0, pos_max=0.1)
    assert math.isclose(c, cap * 0.1, rel_tol=1e-6)


def test_compute_initial_bracket_long_short_and_validation():
    sl, tp = compute_initial_bracket(entry=100.0, atr=2.0, side="long", k_sl=1.5, rr=2.0)
    assert sl == 100.0 - 3.0
    assert tp == 100.0 + 6.0

    sl2, tp2 = compute_initial_bracket(entry=100.0, atr=2.0, side="short", k_sl=1.0, rr=1.0)
    assert sl2 == 102.0
    assert tp2 == 98.0

    try:
        compute_initial_bracket(entry=100.0, atr=-1.0, side="long", k_sl=1.0, rr=1.0)
        assert False, "Expected ValueError for negative atr"
    except ValueError:
        pass
