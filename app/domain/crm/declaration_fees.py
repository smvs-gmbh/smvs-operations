"""Calculate annual self-declaration fee components in CHF."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

SALES_FEES = {
    "JG-0": 0,
    "JG-1": 2_000,
    "JG-3": 5_000,
    "JG-10": 15_000,
    "JG-30": 20_000,
    "JG-50": 25_000,
    "JG-70": 30_000,
    "JG-100": 40_000,
    "JG-150": 50_000,
    "JG-200": 60_000,
    "JG-300": 70_000,
}
QUANTITY_TIERS = (
    ("VG-001", 50_000, Decimal("0.009")),
    ("VG-002", 1_000_000, Decimal("0.007")),
    ("VG-003", 2_000_000, Decimal("0.005")),
    ("VG-004", None, Decimal("0.003")),
)
DEFAULT_BASE_FEE = Decimal("1500.00")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class DeclarationFees:
    base_amount: Decimal
    quantity_group: str
    quantity_amount: Decimal
    sales_amount: Decimal

    @property
    def total(self):
        return self.base_amount + self.quantity_amount + self.sales_amount


def calculate_fees(packs: int, sales_group: str, base_fee: Decimal = DEFAULT_BASE_FEE):
    if type(packs) is not int or packs < 0:
        raise ValueError("Enter a whole, non-negative pack count.")
    if sales_group not in SALES_FEES:
        raise ValueError("Choose a known RX sales group.")
    if not base_fee.is_finite() or base_fee < 0 or base_fee != base_fee.quantize(CENT):
        raise ValueError("Enter a valid base fee in CHF to the nearest cent.")

    lower = 0
    quantity = Decimal(0)
    for group, upper, rate in QUANTITY_TIERS:
        end = min(packs, upper) if upper is not None else packs
        quantity += (end - lower) * rate
        if end == packs:
            return DeclarationFees(
                base_fee.quantize(CENT),
                group,
                quantity.quantize(CENT, rounding=ROUND_HALF_UP),
                Decimal(SALES_FEES[sales_group]).quantize(CENT),
            )
        lower = end
