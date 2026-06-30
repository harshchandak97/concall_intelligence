#!/usr/bin/env python3
"""lib_fx.py — offline historical USD/INR, by calendar quarter (2013–2025).

A USD revenue/PAT target ($1bn by FY28) must be converted to ₹ crore before it can
become a CAGR against a ₹-crore base. USD/INR has drifted from ~55 (2013) to ~85
(2025), so a single hardcoded rate biases every foreign-currency target by up to
~50% depending on the call's vintage. We convert at the USD/INR on the CALL date
(the moment the guidance was given) and hold it over the horizon — future FX is
unknowable, so the call-date spot is the standard simplifying anchor.

Quarterly granularity is deliberate: the conversion is approximate by nature (a
few-% FX error is immaterial to a multi-year CAGR), and a quarter-average smooths
intraday noise while still capturing the big regime moves (2013 taper tantrum,
2018 EM selloff, 2020 COVID spike, 2022 depreciation). Fully offline so a frozen
run is reproducible — no network, no API drift.

Values are approximate calendar-quarter AVERAGE USD/INR.
"""
from __future__ import annotations

# calendar-quarter average USD/INR
_USDINR_Q = {
    (2013, 1): 54.3, (2013, 2): 56.5, (2013, 3): 61.5, (2013, 4): 62.0,
    (2014, 1): 61.8, (2014, 2): 59.8, (2014, 3): 60.6, (2014, 4): 61.9,
    (2015, 1): 62.2, (2015, 2): 63.5, (2015, 3): 64.9, (2015, 4): 65.9,
    (2016, 1): 67.5, (2016, 2): 66.9, (2016, 3): 66.9, (2016, 4): 67.5,
    (2017, 1): 66.9, (2017, 2): 64.5, (2017, 3): 64.3, (2017, 4): 64.7,
    (2018, 1): 64.3, (2018, 2): 67.1, (2018, 3): 70.1, (2018, 4): 72.6,
    (2019, 1): 70.5, (2019, 2): 69.6, (2019, 3): 71.0, (2019, 4): 71.2,
    (2020, 1): 72.5, (2020, 2): 75.9, (2020, 3): 74.4, (2020, 4): 73.8,
    (2021, 1): 72.8, (2021, 2): 73.8, (2021, 3): 74.0, (2021, 4): 74.8,
    (2022, 1): 75.3, (2022, 2): 77.3, (2022, 3): 79.7, (2022, 4): 81.5,
    (2023, 1): 82.3, (2023, 2): 82.0, (2023, 3): 82.7, (2023, 4): 83.3,
    (2024, 1): 82.9, (2024, 2): 83.4, (2024, 3): 83.7, (2024, 4): 84.5,
    (2025, 1): 86.4, (2025, 2): 85.6, (2025, 3): 86.0, (2025, 4): 86.5,
}
_DEFAULT = 83.4  # ~FY24 average, used only for unparseable/out-of-range dates


def usdinr_on(date_str: str) -> float:
    """USD/INR on `date_str` ('YYYY-MM-DD'), resolved to its calendar quarter.
    Out-of-table dates clamp to the nearest available quarter."""
    s = (date_str or "").strip()
    try:
        year = int(s[0:4])
        month = int(s[5:7])
    except (ValueError, IndexError):
        return _DEFAULT
    q = (month - 1) // 3 + 1
    if (year, q) in _USDINR_Q:
        return _USDINR_Q[(year, q)]
    # clamp to nearest endpoint of the table
    keys = sorted(_USDINR_Q)
    if (year, q) < keys[0]:
        return _USDINR_Q[keys[0]]
    if (year, q) > keys[-1]:
        return _USDINR_Q[keys[-1]]
    return _DEFAULT


if __name__ == "__main__":
    for d in ("2024-05-15", "2024-06-05", "2018-10-12", "2013-09-01", "2020-04-20"):
        print(f"{d}: USD/INR = {usdinr_on(d)}")
