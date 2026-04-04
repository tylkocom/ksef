from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from ksef2.domain.models.fa3 import (
    AdvanceInvoiceReference,
    AdvanceOrderLine,
    ContactInfo,
    CorrectedInvoiceReference,
    DraftIntent,
    InvoiceOrder,
    InvoiceSettlement,
    InvoiceAddress,
    InvoiceEntity,
    InvoiceHeader,
    KsefInvoice,
    KsefInvoiceBody,
    MarginProcedure,
    SettlementCharge,
    SettlementDeduction,
)
from ksef2.domain.models.fa3.body import (
    GtuCode,
    AdvancePaymentInvoiceContext,
    InvoiceAnnotationsContext,
    CorrectionInvoiceContext,
    InvoiceProcedure,
    InvoiceType,
    SaleCategory,
    VatRate,
    InvoiceRow,
)
from ksef2.infra.mappers.helpers import to_aware_datetime
from ksef2.infra.mappers.invoices.fa3.invoice import to_spec as invoice_to_spec
from ksef2.infra.schema.fa3.models.schemat import Faktura, __NAMESPACE__


class BaseFA3Builder(ABC):
    """Shared FA(3) builder workflow with intent-specific validation hooks."""

    intent: DraftIntent
    invoice_type: InvoiceType

    def __init__(self, *, intent: DraftIntent, invoice_type: InvoiceType) -> None:
        self.intent = intent
        self.invoice_type = invoice_type
        self._header: InvoiceHeader | None = InvoiceHeader()
        self._seller: InvoiceEntity | None = None
        self._buyer: InvoiceEntity | None = None
        self._body: KsefInvoiceBody | None = None
        self._body_data: dict[str, object] | None = None

    def header(
        self, *, generation_timestamp: datetime | str | None = None, system_info: str
    ) -> Self:
        self._header = InvoiceHeader(
            generation_timestamp=to_aware_datetime(
                generation_timestamp or datetime.now()
            ),
            system_info=system_info,
        )
        return self

    def seller(
        self,
        *,
        name: str,
        country_code: str,
        address_line_1: str,
        tax_id: str | None = None,
        address_line_2: str | None = None,
        gln: str | None = None,
        eu_vat_id: str | None = None,
        customer_number: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> Self:
        self._seller = self._build_entity(
            name=name,
            country_code=country_code,
            address_line_1=address_line_1,
            tax_id=tax_id,
            address_line_2=address_line_2,
            gln=gln,
            eu_vat_id=eu_vat_id,
            customer_number=customer_number,
            email=email,
            phone=phone,
        )
        return self

    def seller_model(self, seller: InvoiceEntity) -> Self:
        self._seller = seller
        return self

    def buyer(
        self,
        *,
        name: str,
        country_code: str,
        address_line_1: str,
        tax_id: str | None = None,
        address_line_2: str | None = None,
        gln: str | None = None,
        eu_vat_id: str | None = None,
        customer_number: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> Self:
        self._buyer = self._build_entity(
            name=name,
            country_code=country_code,
            address_line_1=address_line_1,
            tax_id=tax_id,
            address_line_2=address_line_2,
            gln=gln,
            eu_vat_id=eu_vat_id,
            customer_number=customer_number,
            email=email,
            phone=phone,
        )
        return self

    def buyer_model(self, buyer: InvoiceEntity) -> Self:
        self._buyer = buyer
        return self

    def body(
        self,
        *,
        issue_date: date,
        invoice_number: str | None = None,
        currency: str = "PLN",
        issue_place: str | None = None,
        invoice_type: InvoiceType | str | None = None,
        warehouse_documents: Sequence[str] | None = None,
        date_of_supply: date | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> Self:
        requested_type = (
            self.invoice_type
            if invoice_type is None
            else self._coerce_invoice_type(invoice_type)
        )
        if requested_type != self.invoice_type:
            raise ValueError(
                f"{type(self).__name__} is fixed to invoice_type={self.invoice_type.name}"
            )

        self._body_data = {
            "currency": currency,
            "issue_place": issue_place,
            "issue_date": issue_date,
            "invoice_type": self.invoice_type,
            "warehouse_documents": list(warehouse_documents or []),
            "date_of_supply": date_of_supply,
            "period_start": period_start,
            "period_end": period_end,
        }
        if invoice_number is not None:
            self._body_data["invoice_number"] = invoice_number

        self._refresh_body()
        return self

    def missing_steps(self) -> list[str]:
        missing: list[str] = []
        if self._seller is None:
            missing.append("seller")
        if self._buyer is None:
            missing.append("buyer")
        if self._body_data is None:
            missing.append("body")
        if not self._has_content():
            missing.append(self._content_step_name())
        return missing

    def is_ready(self) -> bool:
        return not self.missing_steps()

    def build(self) -> KsefInvoice:
        missing_steps = self.missing_steps()
        if missing_steps:
            raise ValueError(
                f"Cannot build FA(3) invoice. Missing steps: {', '.join(missing_steps)}"
            )

        assert self._header is not None
        assert self._seller is not None
        assert self._buyer is not None
        self._refresh_body(require_content=True)
        assert self._body is not None

        return KsefInvoice(
            invoice_header=self._header,
            seller=self._seller,
            buyer=self._buyer,
            body=self._body,
        )

    def to_spec(self) -> Faktura:
        return invoice_to_spec(self.build())

    def to_xml(
        self,
        *,
        pretty_print: bool = True,
        xml_declaration: bool = True,
        encoding: str = "UTF-8",
    ) -> str:
        serializer = XmlSerializer(
            config=SerializerConfig(
                pretty_print=pretty_print,
                xml_declaration=xml_declaration,
                encoding=encoding,
            )
        )
        return serializer.render(self.to_spec(), ns_map={None: __NAMESPACE__})

    def _refresh_body(self, *, require_content: bool = False) -> None:
        if self._body_data is None:
            self._body = None
            return
        if not self._has_content():
            if require_content:
                raise ValueError(
                    f"Cannot build FA(3) invoice body without {self._content_step_name()}"
                )
            self._body = None
            return

        self._body = KsefInvoiceBody(**self._body_payload())
        self._validate_built_body(self._body)

    def _body_payload(self) -> dict[str, object]:
        assert self._body_data is not None
        return {**self._body_data, **self._content_payload(), **self._body_extras()}

    def _body_extras(self) -> dict[str, object]:
        return {}

    def _validate_built_body(self, body: KsefInvoiceBody) -> None:
        return None

    @abstractmethod
    def _has_content(self) -> bool: ...

    @abstractmethod
    def _content_payload(self) -> dict[str, object]: ...

    @abstractmethod
    def _content_step_name(self) -> str: ...

    @staticmethod
    def _build_entity(
        *,
        name: str,
        country_code: str,
        address_line_1: str,
        tax_id: str | None,
        address_line_2: str | None,
        gln: str | None,
        eu_vat_id: str | None,
        customer_number: str | None,
        email: str | None,
        phone: str | None,
    ) -> InvoiceEntity:
        contact = ContactInfo(email=email, phone=phone) if email or phone else None
        return InvoiceEntity(
            tax_id=tax_id,
            eu_vat_id=eu_vat_id,
            customer_number=customer_number,
            name=name,
            address=InvoiceAddress(
                country_code=country_code,
                address_line_1=address_line_1,
                address_line_2=address_line_2,
                gln=gln,
            ),
            contact=contact,
        )

    @staticmethod
    def _coerce_invoice_type(value: InvoiceType | str) -> InvoiceType:
        if isinstance(value, InvoiceType):
            return value
        try:
            return InvoiceType[value]
        except KeyError:
            return InvoiceType(value)

    @staticmethod
    def _coerce_vat_rate(value: VatRate | str | None) -> VatRate | None:
        if value is None or isinstance(value, VatRate):
            return value
        try:
            return VatRate[value]
        except KeyError:
            pass
        try:
            return VatRate(value)
        except ValueError as exc:
            raise ValueError(
                f"Provided VAT rate: `{value}` is not valid `VatRate` enum member. "
                f"Valid choices are: {', '.join(VatRate.__members__.keys())}"
            ) from exc

    @staticmethod
    def _coerce_sale_category(value: SaleCategory | str) -> SaleCategory:
        if isinstance(value, SaleCategory):
            return value
        try:
            return SaleCategory[value]
        except KeyError:
            pass
        try:
            return SaleCategory(value)
        except ValueError as exc:
            raise ValueError(
                f"Provided sale category: `{value}` is not valid `SaleCategory` enum member. "
                f"Valid choices are: {', '.join(SaleCategory.__members__.keys())}"
            ) from exc

    @staticmethod
    def _coerce_margin_procedure(
        value: MarginProcedure | str,
    ) -> MarginProcedure:
        if isinstance(value, MarginProcedure):
            return value
        try:
            return MarginProcedure[value]
        except KeyError:
            pass
        try:
            return MarginProcedure(value)
        except ValueError as exc:
            raise ValueError(
                f"Provided margin procedure `{value}` is not valid. "
                f"Valid choices are: {', '.join(MarginProcedure.__members__.keys())}"
            ) from exc


class LineInvoiceBuilder(BaseFA3Builder):
    def __init__(self, *, intent: DraftIntent, invoice_type: InvoiceType) -> None:
        super().__init__(intent=intent, invoice_type=invoice_type)
        self._lines: list[InvoiceRow] = []

    def add_line(
        self,
        *,
        name: str,
        quantity: Decimal,
        unit_price_net: Decimal,
        vat_rate: VatRate | str | None = None,
        unit_of_measure: str = "szt",
        supply_date: date | None = None,
        discount_amount: Decimal | None = Decimal("0.00"),
        sale_category: SaleCategory | str = SaleCategory.STANDARD,
        net_amount: Decimal | None = None,
        vat_amount: Decimal | None = None,
        gross_amount: Decimal | None = None,
        unit_price_gross: Decimal | None = None,
        vat_rate_xii: Decimal | None = None,
        annex_15_marker: bool | None = None,
        excise_amount: Decimal | None = None,
        unique_id: str | None = None,
        sku: str | None = None,
        gtin: str | None = None,
        pkwiu: str | None = None,
        cn: str | None = None,
        pkob: str | None = None,
        gtu_code: GtuCode | None = None,
        procedure: InvoiceProcedure | None = None,
        currency_exchange_rate: Decimal | None = None,
        before_correction: bool = False,
    ) -> Self:
        self._lines.append(
            InvoiceRow(
                name=name,
                quantity=quantity,
                unit_price_net=unit_price_net,
                vat_rate=self._coerce_vat_rate(vat_rate),
                unit_of_measure=unit_of_measure,
                supply_date=supply_date,
                discount_amount=discount_amount,
                sale_category=self._coerce_sale_category(sale_category),
                net_amount=net_amount,
                vat_amount=vat_amount,
                gross_amount=gross_amount,
                unit_price_gross=unit_price_gross,
                vat_rate_xii=vat_rate_xii,
                annex_15_marker=annex_15_marker,
                excise_amount=excise_amount,
                unique_id=unique_id,
                sku=sku,
                gtin=gtin,
                pkwiu=pkwiu,
                cn=cn,
                pkob=pkob,
                gtu_code=gtu_code,
                procedure=procedure,
                currency_exchange_rate=currency_exchange_rate,
                before_correction=before_correction,
            )
        )
        self._refresh_body()
        return self

    def add_line_model(self, line: InvoiceRow) -> Self:
        self._lines.append(line)
        self._refresh_body()
        return self

    def replace_lines(self, lines: Sequence[InvoiceRow]) -> Self:
        self._lines = list(lines)
        self._refresh_body()
        return self

    def clear_lines(self) -> Self:
        self._lines = []
        self._refresh_body()
        return self

    def _has_content(self) -> bool:
        return bool(self._lines)

    def _content_payload(self) -> dict[str, object]:
        return {"rows": self._lines}

    def _content_step_name(self) -> str:
        return "rows"


class StandardInvoiceBuilder(LineInvoiceBuilder):
    def __init__(self) -> None:
        super().__init__(intent=DraftIntent.STANDARD, invoice_type=InvoiceType.VAT)


class CorrectionInvoiceBuilder(LineInvoiceBuilder):
    def __init__(
        self,
        *,
        corrected_invoices: Sequence[CorrectedInvoiceReference],
        correction_reason: str | None = None,
    ) -> None:
        super().__init__(
            intent=DraftIntent.CORRECTION, invoice_type=InvoiceType.CORRECTING
        )
        self._corrected_invoices = list(corrected_invoices)
        if not self._corrected_invoices:
            raise ValueError(
                "Correction invoices require at least one corrected invoice reference"
            )
        self._correction_reason = correction_reason

    def correct_line(self, **kwargs: object) -> Self:
        return self.add_line(**kwargs)

    def _body_extras(self) -> dict[str, object]:
        return {
            "correction": CorrectionInvoiceContext(
                corrected_invoices=self._corrected_invoices,
                correction_reason=self._correction_reason,
            ),
        }


class AdvanceInvoiceBuilder(BaseFA3Builder):
    def __init__(self, *, gross_advance_amount: Decimal) -> None:
        super().__init__(intent=DraftIntent.ADVANCE, invoice_type=InvoiceType.ZAL)
        self._gross_advance_amount = gross_advance_amount
        self._order_lines: list[AdvanceOrderLine] = []

    def add_order_line(
        self,
        *,
        gross_amount: Decimal,
        vat_rate: VatRate | str | None,
        name: str | None = None,
        quantity: Decimal | None = None,
        unit_of_measure: str | None = None,
        unit_price_net: Decimal | None = None,
        sale_category: SaleCategory | str = SaleCategory.STANDARD,
        vat_rate_xii: Decimal | None = None,
        annex_15_marker: bool | None = None,
        unique_id: str | None = None,
        sku: str | None = None,
        gtin: str | None = None,
        pkwiu: str | None = None,
        cn: str | None = None,
        pkob: str | None = None,
        gtu_code: str | None = None,
        procedure: str | None = None,
        excise_amount: Decimal | None = None,
        before_correction: bool = False,
    ) -> Self:
        self._order_lines.append(
            AdvanceOrderLine(
                gross_amount=gross_amount,
                vat_rate=self._coerce_vat_rate(vat_rate).value
                if self._coerce_vat_rate(vat_rate) is not None
                else None,
                name=name,
                quantity=quantity,
                unit_of_measure=unit_of_measure,
                unit_price_net=unit_price_net,
                sale_category=self._coerce_sale_category(sale_category).value,
                vat_rate_xii=vat_rate_xii,
                annex_15_marker=annex_15_marker,
                unique_id=unique_id,
                sku=sku,
                gtin=gtin,
                pkwiu=pkwiu,
                cn=cn,
                pkob=pkob,
                gtu_code=gtu_code,
                procedure=procedure,
                excise_amount=excise_amount,
                before_correction=before_correction,
            )
        )
        self._refresh_body()
        return self

    def add_line(self, **kwargs: object) -> Self:
        return self.add_order_line(**kwargs)

    def add_order_line_model(self, line: AdvanceOrderLine) -> Self:
        self._order_lines.append(line)
        self._refresh_body()
        return self

    def replace_order_lines(self, lines: Sequence[AdvanceOrderLine]) -> Self:
        self._order_lines = list(lines)
        self._refresh_body()
        return self

    def clear_order_lines(self) -> Self:
        self._order_lines = []
        self._refresh_body()
        return self

    def _has_content(self) -> bool:
        return bool(self._order_lines)

    def _content_payload(self) -> dict[str, object]:
        return {
            "order": InvoiceOrder(
                total_value=self._gross_advance_amount,
                order_lines=self._order_lines,
            )
        }

    def _content_step_name(self) -> str:
        return "order_lines"

    def _validate_built_body(self, body: KsefInvoiceBody) -> None:
        if body.total_gross != self._gross_advance_amount:
            raise ValueError(
                "Advance invoice gross amount must equal the sum of order line gross amounts"
            )


class SettlementInvoiceBuilder(LineInvoiceBuilder):
    def __init__(
        self, *, advance_invoice_references: Sequence[AdvanceInvoiceReference]
    ) -> None:
        super().__init__(intent=DraftIntent.SETTLEMENT, invoice_type=InvoiceType.ROZ)
        self._advance_invoice_references = list(advance_invoice_references)
        if not self._advance_invoice_references:
            raise ValueError(
                "Settlement invoices require at least one advance invoice reference"
            )
        self._settlement_charges: list[SettlementCharge] = []
        self._settlement_deductions: list[SettlementDeduction] = []

    def add_charge(self, *, amount: Decimal, reason: str) -> Self:
        self._settlement_charges.append(SettlementCharge(amount=amount, reason=reason))
        self._refresh_body()
        return self

    def add_deduction(self, *, amount: Decimal, reason: str) -> Self:
        self._settlement_deductions.append(
            SettlementDeduction(amount=amount, reason=reason)
        )
        self._refresh_body()
        return self

    def _body_extras(self) -> dict[str, object]:
        return {
            "advance": AdvancePaymentInvoiceContext(
                advance_invoice_references=self._advance_invoice_references,
            ),
            "settlement": InvoiceSettlement(
                charges=self._settlement_charges,
                deductions=self._settlement_deductions,
            ),
        }


class MarginInvoiceBuilder(LineInvoiceBuilder):
    def __init__(self, *, margin_procedure: MarginProcedure | str) -> None:
        super().__init__(intent=DraftIntent.MARGIN, invoice_type=InvoiceType.VAT)
        self._margin_procedure = self._coerce_margin_procedure(margin_procedure)

    def add_line(
        self,
        *,
        name: str,
        quantity: Decimal,
        unit_price_net: Decimal,
        vat_rate: VatRate | str | None = None,
        sale_category: SaleCategory | str = SaleCategory.MARGIN,
        **kwargs: object,
    ) -> Self:
        if vat_rate is not None:
            raise ValueError(
                "Margin invoices cannot contain VAT rates on invoice lines"
            )
        return super().add_line(
            name=name,
            quantity=quantity,
            unit_price_net=unit_price_net,
            vat_rate=None,
            sale_category=SaleCategory.MARGIN,
            **kwargs,
        )

    def _body_extras(self) -> dict[str, object]:
        return {
            "annotations": InvoiceAnnotationsContext(
                margin_procedure=self._margin_procedure
            )
        }


class FA3InvoiceBuilder(StandardInvoiceBuilder):
    """Backward-compatible entry point for standard FA(3) invoices."""

    @classmethod
    def standard(cls) -> StandardInvoiceBuilder:
        return StandardInvoiceBuilder()

    @classmethod
    def correction(
        cls,
        *,
        corrected_invoice_number: str,
        corrected_issue_date: date,
        corrected_ksef_id: str | None = None,
        corrected_outside_ksef: bool = False,
        correction_reason: str | None = None,
    ) -> CorrectionInvoiceBuilder:
        return CorrectionInvoiceBuilder(
            corrected_invoices=[
                CorrectedInvoiceReference(
                    issue_date=corrected_issue_date,
                    invoice_number=corrected_invoice_number,
                    ksef_id=corrected_ksef_id,
                    outside_ksef=corrected_outside_ksef,
                )
            ],
            correction_reason=correction_reason,
        )

    @classmethod
    def advance(cls, *, gross_advance_amount: Decimal) -> AdvanceInvoiceBuilder:
        return AdvanceInvoiceBuilder(gross_advance_amount=gross_advance_amount)

    @classmethod
    def settlement(
        cls, *, advance_invoice_references: Sequence[AdvanceInvoiceReference]
    ) -> SettlementInvoiceBuilder:
        return SettlementInvoiceBuilder(
            advance_invoice_references=advance_invoice_references
        )

    @classmethod
    def margin(cls, *, margin_procedure: MarginProcedure | str) -> MarginInvoiceBuilder:
        return MarginInvoiceBuilder(margin_procedure=margin_procedure)
