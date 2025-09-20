def test_kelly_position_size_basic():
    from trader.position_sizer import kelly_position_size

    capital = 1000.0
    win_rate = 0.6  # p
    avg_win = 10.0
    avg_loss = 10.0
    score = 1.0
    max_score = 1.0

    pos = kelly_position_size(
        capital=capital,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        score=score,
        max_score=max_score,
        f_max=0.2,
        pos_min=0.0,
        pos_max=1.0,
    )

    # Kelly for p=0.6, b=1 -> f* = 0.2; conf=1.0 -> 1000 * 0.2 = 200
    assert abs(pos - 200.0) < 1e-9


def test_kelly_position_size_clamped():
    from trader.position_sizer import kelly_position_size

    capital = 1000.0
    win_rate = 0.9
    avg_win = 30.0
    avg_loss = 10.0  # b=3
    score = 1.0
    max_score = 1.0

    pos = kelly_position_size(
        capital=capital,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        score=score,
        max_score=max_score,
        f_max=0.2,
        pos_min=0.0,
        pos_max=1.0,
    )

    # Raw f* would be ~0.8667 but must clamp to 0.2
    assert abs(pos - 200.0) < 1e-9


def test_kelly_position_size_monotonic_in_score():
    from trader.position_sizer import kelly_position_size

    capital = 1000.0
    win_rate = 0.6
    avg_win = 10.0
    avg_loss = 10.0
    max_score = 1.0

    pos_lo = kelly_position_size(
        capital=capital,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        score=0.2,
        max_score=max_score,
        f_max=0.2,
        pos_min=0.0,
        pos_max=1.0,
    )
    pos_hi = kelly_position_size(
        capital=capital,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        score=0.8,
        max_score=max_score,
        f_max=0.2,
        pos_min=0.0,
        pos_max=1.0,
    )

    assert pos_hi > pos_lo


