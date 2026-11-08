from decimal import Decimal

import pytest

from app.domain.crm.declaration_fees import calculate_fees


@pytest.mark.parametrize(
    ("packs", "group", "amount"),
    [
        (0, "VG-001", "0.00"),
        (50_000, "VG-001", "450.00"),
        (50_001, "VG-002", "450.01"),
        (1_000_000, "VG-002", "7100.00"),
        (1_000_001, "VG-003", "7100.01"),
        (2_000_000, "VG-003", "12100.00"),
        (2_000_002, "VG-004", "12100.01"),
    ],
)
def test_quantity_fee_boundaries(packs, group, amount):
    fees = calculate_fees(packs, "JG-0")
    assert fees.quantity_group == group
    assert fees.quantity_amount == Decimal(amount)


def test_base_override_sales_fee_and_validation():
    fees = calculate_fees(50_000, "JG-300", Decimal("1800.00"))
    assert fees.total == Decimal("72250.00")
    with pytest.raises(ValueError, match="sales group"):
        calculate_fees(0, "JG-301")
    with pytest.raises(ValueError, match="pack count"):
        calculate_fees(-1, "JG-0")
