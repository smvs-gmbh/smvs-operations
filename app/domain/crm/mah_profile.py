"""MAH profile fields and defaults from the preserved Airtable row."""

import re
from datetime import date
from urllib.parse import urlencode

PROFILE_GROUPS = {
    "Company summary": (
        ("company_summary", "Company summary", "Company summary"),
        ("company_size", "Company size", "Company Size"),
    ),
    "General": (
        ("vat_number", "VAT number", "VAT Number"),
        ("domain", "Domain", "Domain"),
        ("status", "Status", "Status"),
    ),
    "Address": (
        ("street", "Street", "Street"),
        (
            "additional_address",
            "Additional address information",
            "Additional address information",
        ),
        ("postal_code", "Postal code", "Postal Code"),
        ("city", "City", "City"),
        ("country", "Country", "Billing country"),
        ("phone", "Phone", "Phone"),
    ),
    "Invoice information": (
        ("discount", "Discount to be applied", "Discount to be applied"),
        ("purchase_order_number", "Purchase order number", "Purchase Order Number"),
        ("invoice_email", "Invoice email", "Email invoice"),
        ("payment_platform_url", "Payment platform URL", "Payment Platform URL"),
    ),
}


ASSOCIATIONS = (
    "ASSGP",
    "intergenerika",
    "interpharma",
    "scienceindustries",
    "SVKH",
    "vips",
)

MAH_MAPPED_COLUMNS = {
    header for group in PROFILE_GROUPS.values() for _, _, header in group
} | {
    "Association",
    "Checked",
    "Eligible for invoicing",
    "GLN",
    "MAH Name",
    "Payment Platform",
    "RECORD_ID",
    "Signing Date (from Contract)",
    "UID",
}
MAH_REVIEW_COLUMNS = {
    "Alert contacts",
    "Contract Status (from Agreements)",
    "Parent Company",
    "SPOC",
}


def association_values(value):
    if isinstance(value, str):
        value = value.split(",")
    return list(dict.fromkeys(label.strip() for label in value if label.strip()))


def logo_url(domain, key, *, size=128):
    domain = domain.strip().lower().rstrip(".")
    if (
        not key
        or not key.startswith("pk_")
        or not re.fullmatch(
            r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
            domain,
        )
    ):
        return None
    query = urlencode({"token": key, "format": "png", "size": size})
    return f"https://img.logo.dev/{domain}?{query}"


def profile_defaults(source):
    profile = {
        field: source.get(header, "")
        for group in PROFILE_GROUPS.values()
        for field, _, header in group
    }
    profile["associations"] = association_values(source.get("Association", ""))
    profile["eligible_for_invoicing"] = (
        source.get("Eligible for invoicing", "").strip().casefold() == "checked"
    )
    profile["payment_platform"] = (
        source.get("Payment Platform", "").strip().casefold() == "checked"
    )
    try:
        day, month, year = map(
            int, source.get("Signing Date (from Contract)", "").split(".")
        )
        profile["signing_date"] = date(year, month, day).isoformat()
    except ValueError:
        profile["signing_date"] = ""
    return profile
