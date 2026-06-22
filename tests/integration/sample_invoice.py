from datetime import date
from decimal import Decimal

from ksef2.fa3 import FA3InvoiceBuilder, VatRate


def build_sample_invoice_xml(
    *,
    seller_nip: str,
    invoice_number: str,
    issue_date: date | None = None,
    buyer_nip: str | None = None,
) -> bytes:
    issued_on = issue_date or date.today()
    buyer_country_code = "PL" if buyer_nip is not None else "DE"

    builder = (
        FA3InvoiceBuilder()
        .header(system_info="ksef2 integration test")
        .seller(
            name="Integration Test Seller",
            tax_id=seller_nip,
            country_code="PL",
            address_line_1="ul. Testowa 1",
            address_line_2="00-001 Warszawa",
        )
        .buyer(
            name="Integration Test Buyer",
            tax_id=buyer_nip,
            country_code=buyer_country_code,
            address_line_1="Test Street 1",
            address_line_2="10115 Berlin",
        )
        .standard()
        .issue_place("Warszawa")
        .issue_date(issued_on)
        .invoice_number(invoice_number)
        .rows()
        .add_line(
            name="Integration test service",
            supply_date=issued_on,
            unit_of_measure="szt.",
            quantity=Decimal("1"),
            unit_price_net=Decimal("100.00"),
            vat_rate=VatRate.VAT_23,
        )
        .done()
        .done()
    )

    return builder.to_xml().encode("utf-8")
