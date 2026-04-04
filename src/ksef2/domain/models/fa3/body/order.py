from decimal import Decimal, ROUND_HALF_UP
from typing import Self

from pydantic import Field, field_validator, model_validator

from ksef2.domain.models import KSeFBaseModel


def round_pln(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class InvoiceOrderLine(KSeFBaseModel):
    """FA(3) order line used inside the invoice order block.

    References:
        schemat.FakturaFaZamowienieZamowienieWiersz

    Maps:
        name - p_7_z (str)
        quantity - p_8_bz (Decimal)
        unit_of_measure - p_8_az (str)
        gross_amount - wartosc used to derive p_11_netto_z/p_11_vat_z
        vat_rate - p_12_z (str)
        sale_category - logical helper for p_12_z variants
        unit_price_net - p_9_az (Decimal)
        net_amount - p_11_netto_z (Decimal)
        vat_amount - p_11_vat_z (Decimal)
        vat_rate_xii - p_12_z_xii (Decimal)
        annex_15_marker - p_12_z_zal_15 (bool)
        unique_id - uu_idz (str)
        sku - indeks_z (str)
        gtin - gtinz (str)
        pkwiu - pkwi_uz (str)
        cn - cnz (str)
        pkob - pkobz (str)
        gtu_code - gtuz (str)
        procedure - procedura_z (str)
        excise_amount - kwota_akcyzy_z (Decimal)
        before_correction - stan_przed_z (bool)
    """

    name: str | None = Field(default=None, description="p_7_z")
    quantity: Decimal | None = Field(default=None, description="p_8_bz")
    unit_of_measure: str | None = Field(default=None, description="p_8_az")
    gross_amount: Decimal = Field(description="Gross value of the order row")
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
    def compute_financial_fields(self) -> Self:
        vat_percent = self._vat_percent()
        if self.net_amount is None:
            if vat_percent is None:
                self.net_amount = self.gross_amount
            else:
                divisor = Decimal("1.00") + vat_percent
                self.net_amount = round_pln(self.gross_amount / divisor)

        if self.vat_amount is None:
            self.vat_amount = round_pln(self.gross_amount - self.net_amount)

        if self.unit_price_net is None and self.quantity not in {None, Decimal("0.00")}:
            assert self.quantity is not None, "quantity must be provided"
            self.unit_price_net = self.net_amount / self.quantity

        return self

    def _vat_percent(self) -> Decimal | None:
        if self.vat_rate in {"23", "22", "8", "7", "5", "4"}:
            assert self.vat_rate is not None
            return Decimal(self.vat_rate) / Decimal("100")
        return None


class InvoiceOrder(KSeFBaseModel):
    """FA(3) invoice order block.

    References:
        schemat.FakturaFaZamowienie

    Maps:
        total_value - wartosc_zamowienia (Decimal)
        order_lines - zamowienie_wiersz List(FakturaFaZamowienieZamowienieWiersz)
    """

    total_value: Decimal | None = None
    order_lines: list[InvoiceOrderLine] = Field(min_length=1)

    @field_validator("total_value")
    @classmethod
    def round_total_value(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value <= Decimal("0.00"):
            raise ValueError("total_value must be greater than zero")
        return round_pln(value)

    @model_validator(mode="after")
    def validate_and_populate_total(self) -> Self:
        computed_total = sum(
            (line.gross_amount for line in self.order_lines),
            start=Decimal("0.00"),
        )

        if self.total_value is not None and self.total_value != computed_total:
            raise ValueError(
                "gross amount must equal the sum of order line gross amounts"
            )

        if self.total_value is None:
            self.total_value = computed_total

        return self


AdvanceOrderLine = InvoiceOrderLine
