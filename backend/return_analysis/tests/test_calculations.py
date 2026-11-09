from datetime import date

import pytest

from return_analysis import calculations as c


def test_simple_returns():
    assert c.gross_return(1000, 1100) == pytest.approx(0.10)
    assert c.net_return(1000, 1100, 20) == pytest.approx(0.08)
    assert c.gross_return(0, 10) is None
    assert c.gross_return(1000, None) is None


def test_annualise():
    assert c.annualise(0.21, 2) == pytest.approx(0.10)
    assert c.annualise(0.1, None) is None
    assert c.annualise(-1.5, 1) == -1.0


def test_irr_known_value():
    # -100 now, +110 one period later -> 10%
    assert c.irr([-100, 110]) == pytest.approx(0.10, abs=1e-6)


def test_irr_refuses_incomplete_flows():
    assert c.irr([-100]) is None
    assert c.irr([-100, -50]) is None   # no inflow
    assert c.irr([100, 50]) is None     # no outflow


def test_xirr_matches_annual_rate():
    r = c.xirr([-1000, 1100], [date(2020, 1, 1), date(2021, 1, 1)])
    assert r == pytest.approx(0.10, abs=2e-3)
    assert c.xirr([-1000], [date(2020, 1, 1)]) is None
    assert c.xirr([-1000, 1100], [date(2020, 1, 1)]) is None


def test_hhi():
    assert c.herfindahl([50, 50]) == pytest.approx(5000)
    assert c.herfindahl([100]) == pytest.approx(10000)
    assert c.herfindahl([0, 0]) is None
    assert c.effective_number(5000) == pytest.approx(2)
