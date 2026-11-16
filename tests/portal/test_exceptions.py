import pytest
from sqlalchemy import select

from app.core.db.models import ImportMutex
from app.domain.exceptions.mapping import MUTEX, publish_exceptions
from app.domain.models import CRMEndUser, LocalOrganisation
from app.portal.exception_routes import router
from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page


@pytest.fixture
def exceptions_portal(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory() as s:
        s.add(ImportMutex(import_key=MUTEX))
        s.commit()
    return client, factory


def test_empty_list_and_filter_validation(exceptions_portal):
    client, _ = exceptions_portal
    assert "No exceptions have been published" in client.get("/exceptions").text
    assert client.get("/exceptions?start=2026-10-10&end=2026-10-01").status_code == 422
    assert client.get("/exceptions/999").status_code == 404
    assert "No alerts or complete query days" in client.get("/exceptions/trends").text


def test_trends_and_drill_down_share_alert_and_country_filters(exceptions_portal):
    import re
    from html import unescape

    from app.domain.participants.mapping import MUTEX as participant_mutex
    from app.domain.participants.mapping import publish_participants
    from tests.domain.test_participants import source

    client, factory = exceptions_portal
    with factory.begin() as session:
        session.add(ImportMutex(import_key=participant_mutex))
    publish_participants(
        factory,
        source(
            factory,
            orgs=[
                {
                    "Organisation Id": "5",
                    "Organisation Name": "Test pharmacy in Liechtenstein",
                }
            ],
            locs=[{"Organisation Id": "5", "Location Id": "request-location"}],
        ),
        NS,
    )
    with factory.begin() as session:
        organisation = session.scalar(select(LocalOrganisation))
        session.add(
            CRMEndUser(
                name="Test pharmacy",
                organisation_id=organisation.id,
                profile={"country": "LIE"},
            )
        )
    publish_exceptions(
        factory,
        acquire(
            factory,
            [
                page(
                    [
                        alert("A2-IN-LI", sourceMarket="CH"),
                        alert("A3-IN-LI", errorCode="A3", sourceMarket="CH"),
                        alert("A7-IN-LI", errorCode="A7", sourceMarket="CH"),
                        alert("UNLINKED", organisationID=9, sourceLocationID="other"),
                    ]
                )
            ],
        ),
        NS,
    )
    response = client.get(
        "/exceptions/trends?start=2026-10-01&end=2026-10-31&alert_group=a2-a3&country=LI"
    )
    assert response.status_code == 200
    assert "2026-10, 2 alerts, 30 of 31 days fully covered" in response.text
    assert "Test pharmacy in Liechtenstein" in response.text
    assert "A7 · Pack already" not in response.text
    link = unescape(
        re.search(r'href="(/exceptions\?[^\"]+gtin14=[^\"]+)">', response.text)[1]
    )
    drill_down = client.get(link).text
    assert "A2-IN-LI" in drill_down and "A3-IN-LI" in drill_down
    assert "A7-IN-LI" not in drill_down and "UNLINKED" not in drill_down
    assert (
        client.get("/exceptions/trends?start=2024-01-01&end=2026-10-01").status_code
        == 422
    )


def test_list_detail_originals_and_context_are_safe_and_distinct(exceptions_portal):
    client, factory = exceptions_portal
    publish_exceptions(
        factory,
        acquire(factory, [page([alert(errorMessage="<script>unsafe</script>")])]),
        NS,
    )
    response = client.get("/exceptions?start=2026-10-01&end=2026-10-31")
    assert response.status_code == 200 and "CH-test-001" in response.text
    assert (
        "WRONG NMVS NAME" not in response.text
        and "&lt;script&gt;unsafe&lt;/script&gt;" in response.text
    )
    assert (
        "No exceptions"
        in client.get("/exceptions?start=2026-10-01&end=2026-10-31&q=%25").text
    )
    detail = client.get("/exceptions/1")
    assert (
        detail.status_code == 200
        and "Pack audit trail" in detail.text
        and "storedBatch" not in detail.text
    )
    assert detail.text.index('aria-label="Exception views"') < detail.text.index("<h1")
    assert "BAD" in detail.text and "Lot-001" in detail.text
    assert "request-location" in detail.text and "last-update-location" in detail.text
    assert "WRONG NMVS NAME" not in detail.text and "Root cause analysis" in detail.text
    raw = client.get("/exceptions/1/source")
    assert (
        raw.status_code == 200
        and "WRONG NMVS NAME" in raw.text
        and "Not an investigation action log" in raw.text
    )


def test_unresolved_date_visible_in_separate_filter(exceptions_portal):
    client, factory = exceptions_portal
    publish_exceptions(
        factory, acquire(factory, [page([alert(alertDateTime="unknown")])]), NS
    )
    assert "no valid source timestamp" in client.get("/exceptions").text
    text = client.get("/exceptions?date_quality=unresolved").text
    assert "CH-test-001" in text and "Date unresolved" in text


def test_intermarket_flag_and_source_market_filters_are_independent(exceptions_portal):
    client, factory = exceptions_portal
    publish_exceptions(
        factory,
        acquire(
            factory,
            [
                page(
                    [
                        alert("LOCAL", sourceMarket="CH", isIntermarket=True),
                        alert("FOREIGN", sourceMarket="DE", isIntermarket=None),
                    ]
                )
            ],
        ),
        NS,
    )
    base = "/exceptions?start=2026-10-01&end=2026-10-31"
    local = client.get(base + "&market=CH&intermarket=yes").text
    foreign = client.get(base + "&market=DE&intermarket=unset").text
    assert ">LOCAL</a>" in local and ">FOREIGN</a>" not in local
    assert ">FOREIGN</a>" in foreign and ">LOCAL</a>" not in foreign
    assert "No exceptions" in client.get(base + "&market=DE&intermarket=yes").text
    assert client.get(base + "&intermarket=unknown").status_code == 422


@pytest.mark.parametrize(
    "source_message", ["Packung bereits vernichtet.", "La boîte est déjà détruite."]
)
def test_english_interface_preserves_source_message_language(
    exceptions_portal, source_message
):
    client, factory = exceptions_portal
    publish_exceptions(
        factory, acquire(factory, [page([alert(errorMessage=source_message)])]), NS
    )
    for path in [
        "/exceptions?start=2026-10-01&end=2026-10-31",
        "/exceptions/1",
        "/exceptions/1/source",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert '<html lang="en">' in response.text
        assert source_message in response.text
        assert "Main navigation" in response.text
