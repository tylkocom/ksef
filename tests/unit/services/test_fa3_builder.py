from datetime import date, datetime
from decimal import Decimal

import pytest

from ksef2.domain.models.fa3 import AdvanceInvoiceReference, MarginProcedure
from ksef2.domain.models.fa3.body import SaleCategory, VatRate
from ksef2.infra.schema.fa3.models.elementarne_typy_danych_v10_0_e import Twybor1
from ksef2.infra.schema.fa3.models.schemat import TrodzajFaktury
from ksef2.services import FA3InvoiceBuilder


def _builder_parties(builder):
    return builder.seller(
        name="ACME S.A.",
        tax_id="1234567890",
        country_code="PL",
        address_line_1="ul. Przykladowa 123",
        address_line_2="Warszawa",
        email="billing@acme.test",
    ).buyer(
        name="XYZ GmbH",
        country_code="DE",
        address_line_1="Unter den Linden 1",
        address_line_2="10115 Berlin",
    )


def test_fa3_invoice_builder_builds_standard_invoice_step_by_step() -> None:
    invoice = (
        _builder_parties(FA3InvoiceBuilder())
        .header(
            generation_timestamp=datetime(2026, 3, 30, 8, 15, 0),
            system_info="ACME ERP",
        )
        .body(
            issue_date=date(2026, 3, 29),
            invoice_number="FV/1/2026",
            issue_place="Warszawa",
        )
        .add_line(
            name="Consulting service",
            quantity=Decimal("10"),
            unit_price_net=Decimal("100.00"),
            vat_rate=VatRate.VAT_23,
        )
        .build()
    )

    assert invoice.invoice_header.system_info == "ACME ERP"
    assert invoice.seller.contact is not None
    assert invoice.seller.contact.email == "billing@acme.test"
    assert invoice.body.invoice_number == "FV/1/2026"
    assert len(invoice.body.rows) == 1
    assert invoice.total_net == Decimal("1000.00")
    assert invoice.total_vat == Decimal("230.00")
    assert invoice.total_gross == Decimal("1230.00")


def test_correction_builder_requires_reference_and_maps_kor_nodes() -> None:
    spec = (
        _builder_parties(
            FA3InvoiceBuilder.correction(
                corrected_invoice_number="FV/99/2026",
                corrected_issue_date=date(2026, 3, 1),
                corrected_ksef_id="1234567890-20260301-ABCDEF-ABCDEF-FF",
                correction_reason="Rabat po sprzedazy",
            )
        )
        .body(
            issue_date=date(2026, 3, 29),
            invoice_number="FK/1/2026",
        )
        .correct_line(
            name="Consulting service",
            quantity=Decimal("-1"),
            unit_price_net=Decimal("100.00"),
            vat_rate=VatRate.VAT_23,
            before_correction=True,
        )
        .add_line(
            name="Consulting service",
            quantity=Decimal("1"),
            unit_price_net=Decimal("90.00"),
            vat_rate=VatRate.VAT_23,
        )
        .to_spec()
    )

    assert spec.fa.rodzaj_faktury == TrodzajFaktury.KOR
    assert spec.fa.przyczyna_korekty == "Rabat po sprzedazy"
    assert spec.fa.dane_fa_korygowanej[0].nr_fa_korygowanej == "FV/99/2026"
    assert spec.fa.dane_fa_korygowanej[0].nr_kse_f == Twybor1.VALUE_1
    assert spec.fa.fa_wiersz[0].stan_przed == Twybor1.VALUE_1


def test_advance_builder_maps_rows_to_zamowienie_and_computes_vat_from_gross() -> None:
    spec = (
        _builder_parties(
            FA3InvoiceBuilder.advance(gross_advance_amount=Decimal("1230.00"))
        )
        .body(
            issue_date=date(2026, 3, 29),
            invoice_number="FZ/1/2026",
        )
        .add_order_line(
            name="Dom jednorodzinny",
            quantity=Decimal("1"),
            unit_of_measure="usl",
            gross_amount=Decimal("1230.00"),
            vat_rate=VatRate.VAT_23,
        )
        .to_spec()
    )

    assert spec.fa.rodzaj_faktury == TrodzajFaktury.ZAL
    assert spec.fa.fa_wiersz == []
    assert spec.fa.zamowienie is not None
    assert spec.fa.zamowienie.wartosc_zamowienia == "1230.00"
    assert spec.fa.zamowienie.zamowienie_wiersz[0].p_7_z == "Dom jednorodzinny"
    assert spec.fa.zamowienie.zamowienie_wiersz[0].p_11_netto_z == "1000.00"
    assert spec.fa.zamowienie.zamowienie_wiersz[0].p_11_vat_z == "230.00"
    assert spec.fa.p_15 == "1230.00"


def test_advance_builder_fails_fast_when_gross_total_does_not_match_declared_amount() -> (
    None
):
    with pytest.raises(ValueError, match="gross amount must equal the sum"):
        (
            _builder_parties(
                FA3InvoiceBuilder.advance(gross_advance_amount=Decimal("1000.00"))
            )
            .body(
                issue_date=date(2026, 3, 29),
                invoice_number="FZ/2/2026",
            )
            .add_order_line(
                name="Projekt",
                gross_amount=Decimal("1230.00"),
                vat_rate=VatRate.VAT_23,
            )
        )


def test_settlement_builder_maps_advance_references_and_deductions() -> None:
    spec = (
        _builder_parties(
            FA3InvoiceBuilder.settlement(
                advance_invoice_references=[
                    AdvanceInvoiceReference(
                        ksef_id="1234567890-20260301-ABCDEF-ABCDEF-FF",
                        deduction_amount=Decimal("500.00"),
                        deduction_reason="Rozliczenie faktury zaliczkowej nr 1",
                    )
                ]
            )
        )
        .body(
            issue_date=date(2026, 3, 29),
            invoice_number="FR/1/2026",
        )
        .add_line(
            name="Koncowa usluga wdrozeniowa",
            quantity=Decimal("1"),
            unit_price_net=Decimal("1000.00"),
            vat_rate=VatRate.VAT_23,
        )
        .add_charge(amount=Decimal("17.00"), reason="Oplata skarbowa")
        .to_spec()
    )

    assert spec.fa.rodzaj_faktury == TrodzajFaktury.ROZ
    assert spec.fa.faktura_zaliczkowa[0].nr_kse_ffa_zaliczkowej is not None
    assert spec.fa.rozliczenie is not None
    assert spec.fa.rozliczenie.suma_obciazen == "17.00"
    assert spec.fa.rozliczenie.suma_odliczen == "500.00"
    assert spec.fa.rozliczenie.do_zaplaty == "747.00"


def test_margin_builder_forbids_vat_rate_and_sets_margin_annotation() -> None:
    builder = _builder_parties(
        FA3InvoiceBuilder.margin(
            margin_procedure=MarginProcedure.USED_GOODS,
        )
    ).body(
        issue_date=date(2026, 3, 29),
        invoice_number="FM/1/2026",
    )

    with pytest.raises(ValueError, match="cannot contain VAT rates"):
        builder.add_line(
            name="Towar uzywany",
            quantity=Decimal("1"),
            unit_price_net=Decimal("1000.00"),
            vat_rate=VatRate.VAT_23,
        )

    spec = builder.add_line(
        name="Towar uzywany",
        quantity=Decimal("1"),
        unit_price_net=Decimal("1000.00"),
        sale_category=SaleCategory.MARGIN,
    ).to_spec()

    assert spec.fa.rodzaj_faktury == TrodzajFaktury.VAT
    assert spec.fa.fa_wiersz[0].p_12 is None
    assert spec.fa.adnotacje.pmarzy.p_pmarzy == Twybor1.VALUE_1
    assert spec.fa.adnotacje.pmarzy.p_pmarzy_3_1 == Twybor1.VALUE_1
