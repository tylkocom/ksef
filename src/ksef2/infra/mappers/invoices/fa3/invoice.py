"""Mappings from FA(3) invoice aggregates to generated root schema models."""

from decimal import Decimal
from functools import singledispatch
from typing import overload, assert_never

from pydantic import BaseModel
from ksef2.domain.models.fa3.body import (
    KsefInvoiceBody,
    InvoiceType,
    GtuCode,
    InvoiceProcedure,
)
from ksef2.domain.models.fa3 import InvoiceLine, KsefInvoice
from ksef2.infra.mappers.invoices.fa3.buyer import to_spec as buyer_to_spec
from ksef2.infra.mappers.invoices.fa3.header import to_spec as header_to_spec
from ksef2.infra.mappers.invoices.fa3.seller import to_spec as seller_to_spec
from ksef2.infra.schema.fa3.models.elementarne_typy_danych_v10_0_e import (
    Twybor1,
    Twybor12,
)
from ksef2.infra.schema.fa3.models.schemat import (
    Faktura,
    FakturaFa,
    FakturaFaOkresFa,
    FakturaFaAdnotacje,
    FakturaFaAdnotacjeNoweSrodkiTransportu,
    FakturaFaAdnotacjePmarzy,
    FakturaFaAdnotacjeZwolnienie,
    FakturaFaFaWiersz,
    TkodWaluty,
    TrodzajFaktury,
    TstawkaPodatku,
    Tgtu,
    ToznaczenieProcedury,
)


def _format_decimal(value: Decimal) -> str:
    """Formats Decimal to string for XML serialization."""
    return format(value, "f")


def _opt_dec(value: Decimal) -> str | None:
    """Returns formatted decimal, or None if zero, to keep XML clean by omitting empty tax buckets."""
    if value.is_zero():
        return None
    return _format_decimal(value)


def _map_currency(value: str) -> TkodWaluty:
    try:
        return TkodWaluty(value.upper())
    except ValueError:
        raise ValueError(f"Unsupported FA(3) currency code: {value}") from None


def _map_vat_rate(value: str) -> TstawkaPodatku:
    try:
        return TstawkaPodatku(value)
    except ValueError:
        raise ValueError(f"Unsupported FA(3) VAT rate: {value}") from None


def _map_gtu_code(value: GtuCode) -> Tgtu:
    try:
        return Tgtu(value)
    except ValueError:
        raise ValueError(f"Unsupported FA(3) GTU code: {value}") from None


def _map_procedure(value: InvoiceProcedure) -> ToznaczenieProcedury:
    try:
        return ToznaczenieProcedury(value)
    except ValueError:
        raise ValueError(f"Unsupported FA(3) procedure code: {value}") from None


def _map_line(line: InvoiceLine, row_number: int) -> FakturaFaFaWiersz:

    assert line.vat_amount is not None, (
        "VAT amount is being automatically calculated and must be set"
    )
    vat_amount = line.vat_amount

    assert line.net_amount is not None, (
        "Net amount is being automatically calculated and must be set"
    )
    net_amount = line.net_amount

    return FakturaFaFaWiersz(
        nr_wiersza_fa=row_number,
        uu_id=line.unique_id,
        p_7=line.name,
        p_8_a=line.unit_of_measure,
        p_8_b=_format_decimal(line.quantity),
        p_9_a=_format_decimal(line.unit_price_net),
        p_9_b=_format_decimal(line.unit_price_gross)
        if line.unit_price_gross is not None
        else None,
        p_10=_format_decimal(line.discount_amount)
        if line.discount_amount and line.discount_amount > 0
        else None,
        p_11=_format_decimal(net_amount),
        p_11_vat=_format_decimal(vat_amount),
        p_12=_map_vat_rate(line.vat_rate) if line.vat_rate else None,
        p_12_xii=line.vat_rate_xii if line.vat_rate_xii else None,
        indeks=line.sku,
        gtin=line.gtin,
        pkwi_u=line.pkwiu,
        cn=line.cn,
        pkob=line.pkob,
        gtu=_map_gtu_code(line.gtu_code) if line.gtu_code else None,
        procedura=_map_procedure(line.procedure) if line.procedure else None,
        stan_przed=Twybor1.VALUE_1 if line.before_correction else None,
        # kwota_akcyzy=_format_decimal(line.excise_amount) if line.excise_amount else None
    )


def _map_adnotacje() -> FakturaFaAdnotacje:
    return FakturaFaAdnotacje(
        p_16=Twybor12.VALUE_2,
        p_17=Twybor12.VALUE_2,
        p_18=Twybor12.VALUE_2,
        p_18_a=Twybor12.VALUE_2,
        zwolnienie=FakturaFaAdnotacjeZwolnienie(p_19_n=Twybor1.VALUE_1),
        nowe_srodki_transportu=FakturaFaAdnotacjeNoweSrodkiTransportu(
            p_22_n=Twybor1.VALUE_1
        ),
        p_23=Twybor12.VALUE_2,
        pmarzy=FakturaFaAdnotacjePmarzy(p_pmarzy_n=Twybor1.VALUE_1),
    )


def map_invoice_type(invoice_type: InvoiceType) -> TrodzajFaktury:
    match invoice_type:
        case InvoiceType.VAT:
            return TrodzajFaktury.VAT
        case InvoiceType.CORRECTING:
            return TrodzajFaktury.KOR
        case InvoiceType.ZAL:
            return TrodzajFaktury.ZAL
        case InvoiceType.ROZ:
            return TrodzajFaktury.ROZ
        case InvoiceType.UPR:
            return TrodzajFaktury.UPR
        case InvoiceType.CORRECTING_ZAL:
            return TrodzajFaktury.KOR_ZAL
        case InvoiceType.CORRECTING_ROZ:
            return TrodzajFaktury.KOR_ROZ
        case _ as unreachable:
            assert_never(unreachable)


@overload
def to_spec(request: KsefInvoice) -> Faktura: ...


@overload
def to_spec(request: KsefInvoiceBody) -> FakturaFa: ...


@overload
def to_spec(request: BaseModel) -> object: ...


def to_spec(request: BaseModel) -> object:
    """Convert a root invoice aggregate into the FA(3) Faktura schema."""
    return _to_spec(request)


@singledispatch
def _to_spec(request: BaseModel) -> object:
    raise NotImplementedError(
        f"No mapper registered for {type(request).__name__}. "
        f"Register one with @_to_spec.register"
    )


@_to_spec.register
def _(request: KsefInvoiceBody) -> FakturaFa:
    faktura_fa_okres_fa = None
    if request.period_start and request.period_end:
        faktura_fa_okres_fa = FakturaFaOkresFa(
            p_6_od=request.period_start.isoformat(),
            p_6_do=request.period_end.isoformat(),
        )

    return FakturaFa(
        kod_waluty=_map_currency(request.currency),
        p_1=request.issue_date.isoformat(),
        p_1_m=request.issue_place,
        p_2=request.invoice_number,
        wz=request.warehouse_documents if request.warehouse_documents else [],
        p_6=request.date_of_supply.isoformat() if request.date_of_supply else None,
        okres_fa=faktura_fa_okres_fa,
        # Mapped strictly to the SaleCategory tax buckets using _opt_dec to omit empty buckets
        p_13_1=_opt_dec(request.base_rate_net_total),
        p_14_1=_opt_dec(request.base_rate_vat_total),
        p_13_2=_opt_dec(request.first_reduced_rate_net_total),
        p_14_2=_opt_dec(request.first_reduced_rate_vat_total),
        p_13_3=_opt_dec(request.second_reduced_rate_net_total),
        p_14_3=_opt_dec(request.second_reduced_rate_vat_total),
        p_13_4=_opt_dec(request.taxi_flat_rate_net_total),
        p_14_4=_opt_dec(request.taxi_flat_rate_vat_total),
        p_13_5=_opt_dec(request.special_procedure_xii_net_total),
        p_14_5=_opt_dec(request.special_procedure_xii_vat_total),
        p_13_6_1=_opt_dec(request.zero_rate_domestic_total),
        p_13_6_2=_opt_dec(request.zero_rate_wdt_total),
        p_13_6_3=_opt_dec(request.zero_rate_export_total),
        p_13_7=_opt_dec(request.exempt_total),
        p_13_8=_opt_dec(request.out_of_territory_total),
        p_13_9=_opt_dec(request.article_100_services_total),
        p_13_10=_opt_dec(request.reverse_charge_total),
        p_13_11=_opt_dec(request.margin_total),
        # Total Gross is mandatory, always format to string even if 0.00
        p_15=_format_decimal(request.total_gross),
        # TODO: Implement p_14_1_w etc. when foreign currency to PLN conversion is added to the domain model
        kurs_waluty_z=None,
        adnotacje=_map_adnotacje(),
        rodzaj_faktury=map_invoice_type(request.invoice_type),
        # Finally, build the actual invoice lines
        fa_wiersz=[
            _map_line(line, row_number)
            for row_number, line in enumerate(request.lines, start=1)
        ],
    )


@_to_spec.register
def _(request: KsefInvoice) -> Faktura:
    return Faktura(
        naglowek=header_to_spec(request.invoice_header),
        podmiot1=seller_to_spec(request.seller),
        podmiot2=buyer_to_spec(request.buyer),
        fa=to_spec(request.body),  # Assuming request.details holds the KsefInvoiceBody
    )
