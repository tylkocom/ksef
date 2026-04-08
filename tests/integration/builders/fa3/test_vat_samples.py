from datetime import date, datetime, timezone
import pytest
from decimal import Decimal
from xsdata.formats.dataclass.parsers import XmlParser

from ksef2.domain.models.fa3.body import InvoiceSummaryOverrides
from ksef2.infra.mappers.invoices.fa3.spec.invoice import (
    from_spec as invoice_from_spec,
)
from ksef2.infra.schema.fa3.models.schemat import Faktura
from ksef2.services.builders.fa3.root import StandardInvoiceBuilder
from tests.integration.builders.helpers import load_sample, sample_path

VAT_SAMPLES = [
    "FA_3_Przykład_21.xml",
    "FA_3_Przykład_22.xml",
    "FA_3_Przykład_23.xml",
    "FA_3_Przykład_24.xml",
    "FA_3_Przykład_25.xml",
    "FA_3_Przykład_26.xml",
    "FA_3_Przykład_4.xml",
    "FA_3_Przykład_8.xml",
    "FA_3_Przykład_9.xml",
    "Fa_3_Przykład_19.xml",
    "Fa_3_Przykład_20.xml",
    "KSEF_05_WDT.xml",
    "KSEF_06_EXP.xml",
]


def _build_vat_from_oracle(sample_name: str) -> StandardInvoiceBuilder:
    expected_invoice = invoice_from_spec(load_sample(sample_path(sample_name)))
    builder = StandardInvoiceBuilder()
    _ = builder.header_model(expected_invoice.header)
    _ = builder.seller_model(expected_invoice.seller)
    _ = builder.buyer_model(expected_invoice.buyer)
    for party in expected_invoice.third_parties:
        _ = builder.add_third_party_model(party)
    if expected_invoice.footer is not None:
        _ = builder.footer_model(expected_invoice.footer)
    if expected_invoice.attachment is not None:
        _ = builder.attachment_model(expected_invoice.attachment)
    _ = builder.standard().from_model(expected_invoice.body).done()
    return builder


def _assert_vat_sample(sample_name: str, builder: StandardInvoiceBuilder) -> None:
    parser = XmlParser()
    expected_spec = load_sample(sample_path(sample_name))
    expected_invoice = invoice_from_spec(expected_spec)
    actual_spec = builder.to_spec()
    actual_invoice = invoice_from_spec(actual_spec)
    xml_invoice = invoice_from_spec(
        parser.from_bytes(builder.to_xml().encode("utf-8"), Faktura)
    )

    assert actual_spec.fa.p_2 == expected_spec.fa.p_2
    assert len(actual_spec.fa.fa_wiersz) == len(expected_spec.fa.fa_wiersz)
    assert Decimal(actual_spec.fa.p_15) == Decimal(expected_spec.fa.p_15)
    assert actual_invoice == expected_invoice
    assert xml_invoice == expected_invoice


@pytest.mark.integration
def test_new_fa3_vat_builder_sample_ksef_01_matches_loaded_sample() -> None:
    parser = XmlParser()
    expected_spec = load_sample(sample_path("KSEF_01_VAT_STANDARD.xml"))
    expected_invoice = invoice_from_spec(expected_spec)

    builder = StandardInvoiceBuilder()
    _ = (
        builder.header(
            generation_timestamp=datetime(2025, 12, 15, 10, 30, 0, tzinfo=timezone.utc),
            system_info="KSEF_TEST_SUITE",
        )
        .seller(
            name="TECH-SOLUTIONS sp. z o.o.",
            tax_id="9999999999",
            country_code="PL",
            address_line_1="ul. Marszalkowska 100",
            address_line_2="00-001 Warszawa",
            email="biuro@tech-solutions.pl",
            phone="+48221234567",
        )
        .buyer(
            name="ABC HANDEL sp. z o.o.",
            tax_id="1111111111",
            country_code="PL",
            address_line_1="ul. Poznanska 50",
            address_line_2="60-001 Poznan",
            customer_number="ABC-001",
            email="kontakt@abc-handel.pl",
            phone="+48617654321",
        )
    )

    _ = (
        builder.footer()
        .add_information("TECH-SOLUTIONS sp. z o.o. - Kapital zakladowy: 500 000 PLN")
        .add_registry(
            krs="0000123456",
            regon="146025969",
            bdo="000012345",
        )
        .done()
    )

    _ = (
        builder.standard()
        .issue_date(date(2025, 12, 15))
        .issue_place("Warszawa")
        .invoice_number("FV/2025/12/0001")
        .date_of_supply(date(2025, 12, 10))
        .summary_overrides(
            InvoiceSummaryOverrides(
                base_rate_net_total=Decimal("4065.04"),
                base_rate_vat_total=Decimal("934.96"),
                total_gross=Decimal("5000.00"),
            )
        )
        .rows()
        .add_line_model(expected_invoice.body.rows[0])
        .done()
        .payment()
        .via("bank_transfer")
        .due_on(date(2026, 1, 15))
        .bank_account(
            "PL61109010140000071219812874",
            bank_name="Santander Bank Polska S.A.",
            account_description="PLN",
        )
        .done()
        .done()
    )

    actual_spec = builder.to_spec()
    actual_invoice = invoice_from_spec(actual_spec)
    xml_invoice = invoice_from_spec(
        parser.from_bytes(builder.to_xml().encode("utf-8"), Faktura)
    )

    assert actual_spec.fa.p_2 == expected_spec.fa.p_2
    assert len(actual_spec.fa.fa_wiersz) == len(expected_spec.fa.fa_wiersz)
    assert Decimal(actual_spec.fa.p_15) == Decimal(expected_spec.fa.p_15)

    assert actual_invoice == expected_invoice
    assert xml_invoice == expected_invoice


@pytest.mark.integration
@pytest.mark.parametrize("sample_name", VAT_SAMPLES)
def test_new_fa3_vat_samples(sample_name: str) -> None:
    builder = _build_vat_from_oracle(sample_name)
    _assert_vat_sample(sample_name, builder)
