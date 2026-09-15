from __future__ import annotations

from decimal import Decimal, InvalidOperation

DecimalLike = Decimal | float | int | None


def _as_decimal(value: DecimalLike) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def safe_growth(current: DecimalLike, previous: DecimalLike) -> float | None:
    cur = _as_decimal(current)
    prev = _as_decimal(previous)
    if cur is None or prev is None:
        return None
    if prev == 0:
        return None
    return _to_float((cur - prev) / abs(prev) * Decimal("100"))


def cagr(start: DecimalLike, end: DecimalLike, years: int) -> float | None:
    s = _as_decimal(start)
    e = _as_decimal(end)
    if s is None or e is None or years <= 0:
        return None
    if s <= 0:
        return None
    try:
        ratio = e / s
        if ratio < 0:
            return None
        return _to_float((ratio ** (Decimal(1) / Decimal(years)) - 1) * Decimal("100"))
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None


def normalized_index(series: list[DecimalLike], *, base_index: int = 0) -> list[float | None]:
    if not series:
        return []
    base = _as_decimal(series[base_index] if 0 <= base_index < len(series) else None)
    if base is None or base == 0:
        return [None for _ in series]
    out: list[float | None] = []
    for item in series:
        value = _as_decimal(item)
        if value is None:
            out.append(None)
        else:
            out.append(_to_float(value / base * Decimal("100")))
    return out


def growth_gap(company: DecimalLike, sector: DecimalLike) -> float | None:
    c = _as_decimal(company)
    s = _as_decimal(sector)
    if c is None or s is None:
        return None
    return _to_float(c - s)


def quarterly_yoy(current: DecimalLike, year_ago: DecimalLike) -> float | None:
    return safe_growth(current, year_ago)


def rolling_average(values: list[DecimalLike], window: int) -> list[float | None]:
    if window <= 0:
        return [None for _ in values]
    out: list[float | None] = []
    for i in range(len(values)):
        chunk = values[max(0, i + 1 - window) : i + 1]
        nums = [_as_decimal(v) for v in chunk]
        if any(v is None for v in nums) or len(nums) < window:
            out.append(None)
            continue
        out.append(_to_float(sum(nums, Decimal(0)) / Decimal(window)))  # type: ignore[arg-type]
    return out


def describe_momentum(growths: list[float | None]) -> str | None:
    """Descriptif uniquement — non converti en score. TODO_WAFABAIL_POLICY_VALIDATION."""
    recent = [g for g in growths[-3:] if g is not None]
    if len(recent) < 2:
        return None
    last = recent[-1]
    prev = recent[-2]
    if last < 0:
        return "CONTRACTING"
    if last > prev + 0.3:
        return "ACCELERATING"
    if last < prev - 0.3:
        return "SLOWING"
    return "STABLE"
