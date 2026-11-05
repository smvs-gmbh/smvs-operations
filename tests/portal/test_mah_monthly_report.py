import re

from app.domain.exceptions.mapping import publish_exceptions
from app.domain.mapping import publish
from app.portal.mah_report_routes import router
from tests.domain.test_mapping import GTIN, seed
from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page


def test_monthly_drafts_separate_a2_a3_and_unassigned(exceptions_portal):
    client, factory = exceptions_portal
    client.app.include_router(router)
    publish(factory, *seed(factory), NS)
    source = acquire(
        factory,
        [
            page(
                [
                    alert("A2-MAPPED", productCode=GTIN),
                    alert(
                        "A3-MAPPED",
                        productCode=GTIN,
                        errorCode="A3",
                        serialNumber="Pack-2",
                    ),
                    alert("UNASSIGNED", productCode="07680548790415"),
                    alert("OTHER-CODE", productCode=GTIN, errorCode="A7"),
                ]
            )
        ],
    )
    publish_exceptions(factory, source, NS)
    response = client.get("/reports/mah?month=2026-10")
    assert response.status_code == 200
    assert "3 retained A2/A3 alerts" in response.text
    assert (
        "Schweizer Inhaberin" in response.text
        and "Review unassigned alerts" in response.text
    )
    holder = re.search(r"holder=([1-9][0-9]*)", response.text)[1]
    draft = client.get(f"/reports/mah?month=2026-10&holder={holder}").text
    assert "A2-MAPPED" in draft and "A3-MAPPED" in draft
    assert "Pack-2" in draft and "Inspect upload history" in draft
    assert "UNASSIGNED" not in draft and "OTHER-CODE" not in draft
    unassigned = client.get("/reports/mah?month=2026-10&holder=0").text
    assert "UNASSIGNED" in unassigned and "A2-MAPPED" not in unassigned
    assert client.get("/reports/mah?month=9999-01").status_code == 422
