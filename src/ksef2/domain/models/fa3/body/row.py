from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Literal, Self, assert_never

from pydantic import Field, model_validator

from ksef2.domain.models import KSeFBaseModel


def round_pln(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


Money = Decimal
GtuCode = Literal[
    "GTU_01",
    "GTU_02",
    "GTU_03",
    "GTU_04",
    "GTU_05",
    "GTU_06",
    "GTU_07",
    "GTU_08",
    "GTU_09",
    "GTU_10",
    "GTU_11",
    "GTU_12",
    "GTU_13",
]
InvoiceProcedure = Literal[
    "WSTO_EE",
    "IED",
    "TT_D",
    "I_42",
    "I_63",
    "B_SPV",
    "B_SPV_DOSTAWA",
    "B_MPV_PROWIZJA",
]


class VatRate(StrEnum):
    VAT_23 = "23"
    VAT_22 = "22"
    VAT_8 = "8"
    VAT_7 = "7"
    VAT_5 = "5"
    VAT_4 = "4"
    VAT_3 = "3"
    VAT_0 = "0"
    EXEMPT = "zw"
    NOT_SUBJECT = "np"
    REVERSE_CHARGE = "oo"


class SaleCategory(StrEnum):
    STANDARD = "standard"
    TAXI_FLAT_RATE = "taxi_flat_rate"
    SPECIAL_XII = "special_xii"
    ZERO_DOMESTIC = "zero_domestic"
    ZERO_WDT = "zero_wdt"
    ZERO_EXPORT = "zero_export"
    EXEMPT = "exempt"
    OUT_OF_TERRITORY = "out_of_territory"
    ARTICLE_100 = "article_100"
    REVERSE_CHARGE = "reverse_charge"
    MARGIN = "margin"


class InvoiceRow(KSeFBaseModel):
    name: str = Field(description="p_7: Name of good/service")
    supply_date: date | None = Field(default=None, description="p_6_a: Date of supply")
    unit_price_net: Money = Field(description="p_9_a: Net unit price")
    vat_rate: VatRate | None = Field(
        default=None,
        description="p_12: VAT rate / formal tax marker where applicable",
    )
    unit_of_measure: str = Field(default="szt", description="p_8_a: Unit of measure")
    quantity: Decimal = Field(description="p_8_b: Quantity")
    discount_amount: Money | None = Field(
        default=Decimal("0.00"), description="p_10: Discount amount"
    )

    # --- computed fields ---
    unit_price_gross: Money | None = Field(
        default=None, description="p_9_b: Price with VAT"
    )
    gross_amount: Money | None = Field(
        default=None, description="p_11_a: Gross value of the line"
    )
    net_amount: Money | None = Field(
        default=None, description="p_11: Net value of the line"
    )
    vat_amount: Money | None = Field(
        default=None, description="p_11_vat: VAT amount of the line"
    )

    @model_validator(mode="after")
    def compute_financial_field(self):
        if self.net_amount is None:
            base_net = self.unit_price_net * self.quantity
            self.net_amount = round_pln(base_net) - (
                self.discount_amount or Decimal("0.00")
            )

        if self.vat_amount is None:
            if self.vat_rate in {
                VatRate.VAT_23,
                VatRate.VAT_22,
                VatRate.VAT_8,
                VatRate.VAT_7,
                VatRate.VAT_5,
                VatRate.VAT_4,
            }:
                decimal_vat_rate = (
                    Decimal(self.vat_rate.value) / Decimal("100")
                    if self.vat_rate
                    else Decimal("0.00")
                )
                rate_decimal = decimal_vat_rate
                self.vat_amount = round_pln(self.net_amount * rate_decimal)
            else:
                # for VAT_0, EXEMPT (zw), NOT_SUBJECT (np), REVERSE_CHARGE (oo)
                self.vat_amount = Decimal("0.00")

        if self.gross_amount is None:
            self.gross_amount = round_pln(self.net_amount + self.vat_amount)

        _ = self.validate_tax_logic()

        return self

    vat_rate_xii: Decimal | None = Field(
        default=None, description="p_12_XII: VAT rate XII"
    )
    annex_15_marker: bool | None = Field(
        default=None, description="p_12_ZAL_15: Annex 15 marker"
    )

    sale_category: SaleCategory = Field(
        default=SaleCategory.STANDARD,
        description=(
            "Logical classification used to map the line into KSeF summary buckets "
            "(e.g. standard, WDT 0%, export 0%, exempt, reverse charge, margin)."
        ),
    )

    excise_amount: Money | None = Field(
        default=None, description="kwota_akcyzy: Excise amount"
    )
    unique_id: str | None = Field(default=None, description="uu_id: Unique ID")
    sku: str | None = Field(
        default=None, description="indeks: Internal SKU or additional description"
    )
    gtin: str | None = Field(default=None, description="gtin: Global Trade Item Number")
    pkwiu: str | None = Field(
        default=None, description="pkwi_u: Polish Goods Classification"
    )
    cn: str | None = Field(default=None, description="cn: Nomenclature Code")
    pkob: str | None = Field(
        default=None, description="pkob: Polish Construction Object Classification"
    )

    gtu_code: GtuCode | None = Field(default=None, description="gtu: GTU code")
    procedure: InvoiceProcedure | None = Field(
        default=None, description="procedura: Procedure code"
    )
    currency_exchange_rate: Decimal | None = Field(
        default=None, description="kurs_waluty: Currency exchange rate"
    )
    before_correction: bool = Field(
        default=False,
        description="stan_przed: Marks the row as representing state before correction",
    )

    def validate_tax_logic(self) -> Self:
        self._validate_quantity()
        self._validate_sale_category_rules()
        self._validate_gross_amount_consistency()
        return self

    def _validate_quantity(self) -> None:
        if self.quantity == 0:
            raise ValueError("quantity cannot be zero")

    def _validate_sale_category_rules(self) -> None:
        match self.sale_category:
            case SaleCategory.STANDARD:
                self._validate_standard_sale()
            case SaleCategory.TAXI_FLAT_RATE:
                self._validate_taxi_flat_rate()
            case SaleCategory.ZERO_DOMESTIC:
                self._validate_zero_domestic()
            case SaleCategory.ZERO_WDT:
                self._validate_zero_wdt()
            case SaleCategory.ZERO_EXPORT:
                self._validate_zero_export()
            case SaleCategory.EXEMPT:
                self._validate_exempt()
            case SaleCategory.OUT_OF_TERRITORY:
                self._validate_out_of_territory()
            case SaleCategory.ARTICLE_100:
                self._validate_article_100()
            case SaleCategory.REVERSE_CHARGE:
                self._validate_reverse_charge()
            case SaleCategory.MARGIN:
                self._validate_margin()
            case SaleCategory.SPECIAL_XII:
                self._validate_special_xii()
            case _ as unreachable:  # pyright: ignore[reportUnnecessaryComparison]
                assert_never(unreachable)

    def _validate_standard_sale(self) -> None:
        # Standard domestic taxable sale using ordinary VAT rate buckets.
        # This category maps to the classic KSeF summary fields such as p_13_1..p_13_3 and p_14_1..p_14_3.
        if self.vat_rate not in {
            VatRate.VAT_23,
            VatRate.VAT_22,
            VatRate.VAT_8,
            VatRate.VAT_7,
            VatRate.VAT_5,
        }:
            raise ValueError(
                "STANDARD sale_category requires vat_rate equal to 23, 22, 8, 7, or 5"
            )

    def _validate_taxi_flat_rate(self) -> None:
        # Taxi flat-rate sale is a special tax regime.
        # It should be represented only with the dedicated 4% bucket.
        if self.vat_rate != VatRate.VAT_4:
            raise ValueError("TAXI_FLAT_RATE requires vat_rate='4'")

    def _validate_zero_domestic(self) -> None:
        # Domestic 0% sale, excluding intra-EU supply and export.
        # This maps to p_13_6_1.
        if self.vat_rate != VatRate.VAT_0:
            raise ValueError("ZERO_DOMESTIC requires vat_rate='0'")

    def _validate_zero_wdt(self) -> None:
        # Intra-EU supply of goods taxed at 0%.
        # This maps to p_13_6_2.
        if self.vat_rate != VatRate.VAT_0:
            raise ValueError("ZERO_WDT requires vat_rate='0'")

    def _validate_zero_export(self) -> None:
        # Export sale taxed at 0%.
        # This maps to p_13_6_3.
        if self.vat_rate != VatRate.VAT_0:
            raise ValueError("ZERO_EXPORT requires vat_rate='0'")

    def _validate_exempt(self) -> None:
        # VAT-exempt sale.
        # This maps to p_13_7 and must not be treated as a taxable rate bucket.
        if self.vat_rate != VatRate.EXEMPT:
            raise ValueError("EXEMPT category requires vat_rate='zw'")

    def _validate_out_of_territory(self) -> None:
        # Sale outside the territory of Poland.
        # Usually represented as not subject to Polish VAT and maps to p_13_8.
        if self.vat_rate not in {VatRate.NOT_SUBJECT, None}:
            raise ValueError("OUT_OF_TERRITORY requires vat_rate='np' or None")

    def _validate_article_100(self) -> None:
        # Services reported under Article 100(1)(4).
        # This is a reporting-specific bucket and should be marked as not subject in Poland.
        if self.vat_rate not in {VatRate.NOT_SUBJECT, None}:
            raise ValueError("ARTICLE_100 requires vat_rate='np' or None")

    def _validate_reverse_charge(self) -> None:
        # Reverse-charge sale where the buyer accounts for VAT.
        # This maps to p_13_10 and should not use ordinary VAT sale buckets.
        if self.vat_rate not in {VatRate.REVERSE_CHARGE, None}:
            raise ValueError("REVERSE_CHARGE requires vat_rate='oo' or None")

    def _validate_margin(self) -> None:
        # Margin scheme sale under the dedicated margin procedure.
        # It maps to p_13_11 and must not be represented as a normal VAT rate bucket.
        if self.vat_rate in {
            VatRate.VAT_23,
            VatRate.VAT_22,
            VatRate.VAT_8,
            VatRate.VAT_7,
            VatRate.VAT_5,
            VatRate.VAT_4,
            VatRate.VAT_0,
        }:
            raise ValueError("MARGIN category should not use standard VAT rates")

    def _validate_special_xii(self) -> None:
        # Special Title XII procedure.
        # This category requires the dedicated vat_rate_xii field instead of ordinary VAT rate handling.
        if self.vat_rate_xii is None:
            raise ValueError("SPECIAL_XII requires vat_rate_xii")

    def _validate_gross_amount_consistency(self) -> None:
        # Gross amount, when provided, must equal net amount plus VAT amount.
        if self.gross_amount is not None:
            assert self.net_amount is not None and self.vat_amount is not None, (
                "net_amount and vat_amount must be set when gross_amount is provided"
            )
            expected_gross = self.net_amount + self.vat_amount
            if self.gross_amount != expected_gross:
                raise ValueError(
                    f"gross_amount must equal net_amount + vat_amount ({expected_gross})"
                )
