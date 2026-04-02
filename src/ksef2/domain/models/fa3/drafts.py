from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from ksef2.domain.models import KSeFBaseModel


def round_pln(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class DraftIntent(StrEnum):
    STANDARD = "VAT"
    CORRECTION = "KOR"
    ADVANCE = "ZAL"
    SETTLEMENT = "ROZ"
    MARGIN = "MARZA"


class MarginProcedure(StrEnum):
    TRAVEL_AGENCY = "travel_agency"
    USED_GOODS = "used_goods"
    ARTWORKS = "artworks"
    COLLECTIBLES_AND_ANTIQUES = "collectibles_and_antiques"


class CorrectedInvoiceReference(KSeFBaseModel):
    issue_date: date
    invoice_number: str
    ksef_id: str | None = None
    outside_ksef: bool = False

    @model_validator(mode="after")
    def validate_reference(self) -> "CorrectedInvoiceReference":
        if self.ksef_id and self.outside_ksef:
            raise ValueError("ksef_id and outside_ksef cannot be used together")
        if not self.ksef_id and not self.outside_ksef:
            raise ValueError("Either ksef_id or outside_ksef=True is required")
        return self


class AdvanceInvoiceReference(KSeFBaseModel):
    ksef_id: str | None = None
    invoice_number: str | None = None
    outside_ksef: bool = False
    deduction_amount: Decimal | None = None
    deduction_reason: str | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> "AdvanceInvoiceReference":
        if self.ksef_id and (self.invoice_number or self.outside_ksef):
            raise ValueError(
                "ksef_id cannot be combined with invoice_number/outside_ksef"
            )
        if not self.ksef_id:
            if not self.outside_ksef:
                raise ValueError(
                    "outside_ksef=True is required when advance invoice is not in KSeF"
                )
            if not self.invoice_number:
                raise ValueError(
                    "invoice_number is required for advance invoices outside KSeF"
                )
        if (self.deduction_amount is None) != (self.deduction_reason is None):
            raise ValueError(
                "deduction_amount and deduction_reason must be provided together"
            )
        return self


class SettlementCharge(KSeFBaseModel):
    amount: Decimal
    reason: str

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0.00"):
            raise ValueError("amount must be greater than zero")
        return round_pln(value)


class SettlementDeduction(KSeFBaseModel):
    amount: Decimal
    reason: str

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0.00"):
            raise ValueError("amount must be greater than zero")
        return round_pln(value)


class AdvanceOrderLine(KSeFBaseModel):
    name: str | None = Field(default=None, description="p_7_z")
    quantity: Decimal | None = Field(default=None, description="p_8_bz")
    unit_of_measure: str | None = Field(default=None, description="p_8_az")
    gross_amount: Decimal = Field(description="Gross value of the advanced order row")
    vat_rate: str | None = Field(default=None, description="p_12_z")
    sale_category: str = Field(default="standard")
    unit_price_net: Decimal | None = Field(default=None, description="p_9_az")
    net_amount: Decimal | None = Field(default=None, description="p_11_netto_z")
    vat_amount: Decimal | None = Field(default=None, description="p_11_vat_z")
    vat_rate_xii: Decimal | None = Field(default=None, description="p_12_z_xii")
    annex_15_marker: bool | None = Field(default=None, description="p_12_z_zal_15")
    unique_id: str | None = Field(default=None, description="uu_idz")
    sku: str | None = Field(default=None, description="indeks_z")
    gtin: str | None = Field(default=None, description="gtinz")
    pkwiu: str | None = Field(default=None, description="pkwi_uz")
    cn: str | None = Field(default=None, description="cnz")
    pkob: str | None = Field(default=None, description="pkobz")
    gtu_code: str | None = Field(default=None, description="gtuz")
    procedure: str | None = Field(default=None, description="procedura_z")
    excise_amount: Decimal | None = Field(default=None, description="kwota_akcyzy_z")
    before_correction: bool = Field(default=False, description="stan_przed_z")

    @field_validator("gross_amount")
    @classmethod
    def validate_gross_amount(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0.00"):
            raise ValueError("gross_amount must be greater than zero")
        return round_pln(value)

    @model_validator(mode="after")
    def compute_financial_fields(self) -> "AdvanceOrderLine":
        vat_percent = self._vat_percent()
        if self.net_amount is None:
            if vat_percent is None:
                self.net_amount = self.gross_amount
            else:
                divisor = Decimal("1.00") + vat_percent
                self.net_amount = round_pln(self.gross_amount / divisor)

        if self.vat_amount is None:
            self.vat_amount = round_pln(self.gross_amount - self.net_amount)

        if self.unit_price_net is None and self.quantity not in {None, Decimal("0")}:
            self.unit_price_net = self.net_amount / self.quantity

        return self

    def _vat_percent(self) -> Decimal | None:
        if self.vat_rate in {"23", "22", "8", "7", "5", "4"}:
            assert self.vat_rate is not None
            return Decimal(self.vat_rate) / Decimal("100")
        return None
