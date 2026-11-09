from decimal import Decimal

import pytest

from lending_data.services import parsing as p


def test_parsing_helpers():
    assert p.parse_term_months(" 36 months") == 36
    assert p.to_decimal("13.56%") == Decimal("13.56")
    assert p.to_decimal("") is None
    assert p.parse_employment_years("< 1 year") == 0
    assert p.parse_employment_years("10+ years") == 10
    assert str(p.parse_date("Dec-2015")) == "2015-12-01"
    assert p.standardise_status("Does not meet the credit policy. Status:Charged Off") == "charged_off"
    assert p.standardise_status("Weird") == "unknown"
    with pytest.raises(ValueError):
        p.to_decimal("abc")
    with pytest.raises(ValueError):
        p.to_decimal("inf")
