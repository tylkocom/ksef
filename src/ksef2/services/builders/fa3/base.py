from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, Self, TypeVar

from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from ksef2.domain.models.fa3 import (
    AdvanceInvoiceReference,
    AdvanceOrderLine,
    ContactInfo,
    CorrectedInvoiceReference,
    DraftIntent,
    InvoiceAddress,
    InvoiceEntity,
    InvoiceHeader,
    InvoiceOrder,
    InvoiceSettlement,
    KsefInvoice,
    KsefInvoiceBody,
    MarginProcedure,
    SettlementCharge,
    SettlementDeduction,
)
from ksef2.domain.models.fa3.body import (
    AdvancePaymentInvoiceContext,
    BankAccount,
    CorrectionInvoiceContext,
    CorrectedBuyerEntity,
    CorrectedSellerEntity,
    GtuCode,
    InvoiceAnnotationsContext,
    InvoicePayment,
    InvoiceProcedure,
    InvoiceRow,
    InvoiceTaxExemption,
    InvoiceType,
    NewTransportMeansItem,
    NewTransportSupply,
    PartialAdvancePayment,
    PartialPayment,
    PartialPaymentStatus,
    PaymentForm,
    PaymentTerm,
    PaymentTermDescription,
    SaleCategory,
    VatRate,
)
from ksef2.domain.models.fa3.body.correction import CorrectionEffectType
from ksef2.infra.mappers.helpers import to_aware_datetime
from ksef2.infra.mappers.invoices.fa3.invoice import to_spec as invoice_to_spec
from ksef2.infra.schema.fa3.models.schemat import Faktura, __NAMESPACE__

TBuilder = TypeVar("TBuilder", bound="BaseFA3Builder")
TAdvanceBuilder = TypeVar("TAdvanceBuilder", bound="AdvanceCapableBuilderMixin")
TSettlementBuilder = TypeVar(
    "TSettlementBuilder", bound="SettlementCapableBuilderMixin"
)
TOrderBuilder = TypeVar("TOrderBuilder", bound="AdvanceInvoiceBuilder")


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
        self._body_data: dict[str, object] | None = None
        self._payment: InvoicePayment | None = None
        self._annotations: InvoiceAnnotationsContext | None = None

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
        other_id: str | None = None,
        eori_number: str | None = None,
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
            other_id=other_id,
            eori_number=eori_number,
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
        other_id: str | None = None,
        eori_number: str | None = None,
        customer_number: str | None = None,
        jst_subordinate_unit: bool = False,
        vat_group_member: bool = False,
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
            other_id=other_id,
            eori_number=eori_number,
            customer_number=customer_number,
            jst_subordinate_unit=jst_subordinate_unit,
            vat_group_member=vat_group_member,
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
        return self

    def payment(self: TBuilder) -> "PaymentBuilder[TBuilder]":
        return PaymentBuilder(self, self._payment)

    def annotations(self: TBuilder) -> "AnnotationsBuilder[TBuilder]":
        return AnnotationsBuilder(self, self._annotations)

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

        body = self._materialize_body(require_content=True)
        assert body is not None

        return KsefInvoice(
            invoice_header=self._header,
            seller=self._seller,
            buyer=self._buyer,
            body=body,
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

    def _materialize_body(
        self, *, require_content: bool = False
    ) -> KsefInvoiceBody | None:
        if self._body_data is None:
            return None
        if not self._has_content():
            if require_content:
                raise ValueError(
                    f"Cannot build FA(3) invoice body without {self._content_step_name()}"
                )
            return None

        body = KsefInvoiceBody(**self._body_payload())
        self._validate_built_body(body)
        return body

    def _body_payload(self) -> dict[str, object]:
        assert self._body_data is not None
        return {
            **self._body_data,
            **self._content_payload(),
            **self._common_section_payload(),
            **self._body_section_payload(),
        }

    def _common_section_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self._payment is not None:
            payload["payment"] = self._payment
        if self._annotations is not None:
            payload["annotations"] = self._annotations
        return payload

    def _body_section_payload(self) -> dict[str, object]:
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
        other_id: str | None = None,
        eori_number: str | None = None,
        customer_number: str | None,
        jst_subordinate_unit: bool = False,
        vat_group_member: bool = False,
        email: str | None,
        phone: str | None,
    ) -> InvoiceEntity:
        contact = ContactInfo(email=email, phone=phone) if email or phone else None
        return InvoiceEntity(
            tax_id=tax_id,
            eu_vat_id=eu_vat_id,
            other_id=other_id,
            eori_number=eori_number,
            customer_number=customer_number,
            jst_subordinate_unit=jst_subordinate_unit,
            vat_group_member=vat_group_member,
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
    def _build_address(
        *,
        country_code: str,
        address_line_1: str,
        address_line_2: str | None = None,
        gln: str | None = None,
    ) -> InvoiceAddress:
        return InvoiceAddress(
            country_code=country_code,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            gln=gln,
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
        return self

    def add_line_model(self, line: InvoiceRow) -> Self:
        self._lines.append(line)
        return self

    def replace_lines(self, lines: Sequence[InvoiceRow]) -> Self:
        self._lines = list(lines)
        return self

    def clear_lines(self) -> Self:
        self._lines = []
        return self

    def _has_content(self) -> bool:
        return bool(self._lines)

    def _content_payload(self) -> dict[str, object]:
        return {"rows": list(self._lines)}

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
        if not corrected_invoices:
            raise ValueError(
                "Correction invoices require at least one corrected invoice reference"
            )
        self._correction = CorrectionInvoiceContext(
            corrected_invoices=list(corrected_invoices),
            correction_reason=correction_reason,
        )

    def correct_line(self, **kwargs: object) -> Self:
        return self.add_line(**kwargs)

    def correction(self) -> "CorrectionBuilder[CorrectionInvoiceBuilder]":
        return CorrectionBuilder(self, self._correction)

    def _body_section_payload(self) -> dict[str, object]:
        if self._correction is None:
            return {}
        return {"correction": self._correction}


class AdvanceCapableBuilderMixin:
    _advance: AdvancePaymentInvoiceContext | None

    def advance(self: TAdvanceBuilder) -> "AdvanceBuilder[TAdvanceBuilder]":
        return AdvanceBuilder(self, self._advance)


class SettlementCapableBuilderMixin:
    _settlement: InvoiceSettlement | None

    def settlement(
        self: TSettlementBuilder,
    ) -> "SettlementBuilder[TSettlementBuilder]":
        return SettlementBuilder(self, self._settlement)


class AdvanceInvoiceBuilder(AdvanceCapableBuilderMixin, BaseFA3Builder):
    def __init__(self, *, gross_advance_amount: Decimal) -> None:
        super().__init__(intent=DraftIntent.ADVANCE, invoice_type=InvoiceType.ZAL)
        self._gross_advance_amount = gross_advance_amount
        self._order: InvoiceOrder | None = None
        self._advance: AdvancePaymentInvoiceContext | None = None

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
        vat_rate_value = self._coerce_vat_rate(vat_rate)
        line = AdvanceOrderLine(
            gross_amount=gross_amount,
            vat_rate=vat_rate_value.value if vat_rate_value is not None else None,
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
        return self.add_order_line_model(line)

    def add_line(self, **kwargs: object) -> Self:
        return self.add_order_line(**kwargs)

    def add_order_line_model(self, line: AdvanceOrderLine) -> Self:
        lines = [*(self._order.order_lines if self._order else []), line]
        self._order = InvoiceOrder(
            total_value=self._gross_advance_amount,
            order_lines=lines,
        )
        return self

    def replace_order_lines(self, lines: Sequence[AdvanceOrderLine]) -> Self:
        if not lines:
            self._order = None
            return self
        self._order = InvoiceOrder(
            total_value=self._gross_advance_amount,
            order_lines=list(lines),
        )
        return self

    def clear_order_lines(self) -> Self:
        self._order = None
        return self

    def order(self) -> "OrderBuilder[AdvanceInvoiceBuilder]":
        return OrderBuilder(self, self._order, self._gross_advance_amount)

    def _has_content(self) -> bool:
        return self._order is not None and bool(self._order.order_lines)

    def _content_payload(self) -> dict[str, object]:
        assert self._order is not None
        return {"order": self._order}

    def _content_step_name(self) -> str:
        return "order_lines"

    def _body_section_payload(self) -> dict[str, object]:
        if self._advance is None:
            return {}
        return {"advance": self._advance}


class SettlementInvoiceBuilder(
    AdvanceCapableBuilderMixin, SettlementCapableBuilderMixin, LineInvoiceBuilder
):
    def __init__(
        self, *, advance_invoice_references: Sequence[AdvanceInvoiceReference]
    ) -> None:
        super().__init__(intent=DraftIntent.SETTLEMENT, invoice_type=InvoiceType.ROZ)
        if not advance_invoice_references:
            raise ValueError(
                "Settlement invoices require at least one advance invoice reference"
            )
        self._advance = AdvancePaymentInvoiceContext(
            advance_invoice_references=list(advance_invoice_references)
        )
        self._settlement: InvoiceSettlement | None = None

    def add_charge(self, *, amount: Decimal, reason: str) -> Self:
        settlement = self._settlement or InvoiceSettlement()
        self._settlement = InvoiceSettlement(
            charges=[
                *settlement.charges,
                SettlementCharge(amount=amount, reason=reason),
            ],
            charges_total=None,
            deductions=settlement.deductions,
            deductions_total=settlement.deductions_total,
            amount_due=settlement.amount_due,
            amount_to_settle=settlement.amount_to_settle,
        )
        return self

    def add_deduction(self, *, amount: Decimal, reason: str) -> Self:
        settlement = self._settlement or InvoiceSettlement()
        self._settlement = InvoiceSettlement(
            charges=settlement.charges,
            charges_total=settlement.charges_total,
            deductions=[
                *settlement.deductions,
                SettlementDeduction(amount=amount, reason=reason),
            ],
            deductions_total=None,
            amount_due=settlement.amount_due,
            amount_to_settle=settlement.amount_to_settle,
        )
        return self

    def _body_section_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"advance": self._advance}
        if self._settlement is not None:
            payload["settlement"] = self._settlement
        return payload


class MarginInvoiceBuilder(LineInvoiceBuilder):
    def __init__(self, *, margin_procedure: MarginProcedure | str) -> None:
        super().__init__(intent=DraftIntent.MARGIN, invoice_type=InvoiceType.VAT)
        self._annotations = InvoiceAnnotationsContext(
            margin_procedure=self._coerce_margin_procedure(margin_procedure)
        )

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


class PaymentBuilder(Generic[TBuilder]):
    def __init__(
        self, parent: TBuilder, existing_state: InvoicePayment | None = None
    ) -> None:
        self.parent = parent
        self.model(existing_state)

    def model(self, payment: InvoicePayment | None) -> Self:
        payment = payment.model_copy(deep=True) if payment is not None else None
        self._paid = payment.paid if payment else False
        self._payment_date = payment.payment_date if payment else None
        self._partial_payment_status = (
            payment.partial_payment_status if payment else None
        )
        self._partial_payments = list(payment.partial_payments) if payment else []
        self._payment_terms = list(payment.payment_terms) if payment else []
        self._payment_form = payment.payment_form if payment else None
        self._other_payment_form = payment.other_payment_form if payment else False
        self._payment_description = payment.payment_description if payment else None
        self._bank_accounts = list(payment.bank_accounts) if payment else []
        self._factor_bank_accounts = (
            list(payment.factor_bank_accounts) if payment else []
        )
        self._discount_terms = payment.discount_terms if payment else None
        self._discount_amount = payment.discount_amount if payment else None
        self._payment_link = payment.payment_link if payment else None
        self._ipksef = payment.ipksef if payment else None
        return self

    def via(self, payment_form: PaymentForm) -> Self:
        self._payment_form = payment_form
        return self

    def already_paid(self, payment_date: date | None = None) -> Self:
        self._paid = True
        if payment_date is not None:
            self._payment_date = payment_date
        return self

    def unpaid(self) -> Self:
        self._paid = False
        self._payment_date = None
        return self

    def payment_date(self, payment_date: date | None) -> Self:
        self._payment_date = payment_date
        return self

    def partial_payment_status(self, status: PartialPaymentStatus | None) -> Self:
        self._partial_payment_status = status
        return self

    def other_form(self, enabled: bool = True) -> Self:
        self._other_payment_form = enabled
        return self

    def description(self, description: str | None) -> Self:
        self._payment_description = description
        return self

    def due_on(self, due_date: date) -> Self:
        self._payment_terms.append(PaymentTerm(due_date=due_date))
        return self

    def due_with_description(
        self,
        *,
        quantity: int,
        unit: str,
        starting_event: str,
        due_date: date | None = None,
    ) -> Self:
        self._payment_terms.append(
            PaymentTerm(
                due_date=due_date,
                due_date_description=PaymentTermDescription(
                    quantity=quantity,
                    unit=unit,
                    starting_event=starting_event,
                ),
            )
        )
        return self

    def add_term_model(self, term: PaymentTerm) -> Self:
        self._payment_terms.append(term)
        return self

    def clear_terms(self) -> Self:
        self._payment_terms = []
        return self

    def add_partial_payment(
        self,
        *,
        amount: Decimal,
        payment_date: date,
        payment_form: PaymentForm | None = None,
        other_payment_form: bool = False,
        payment_description: str | None = None,
    ) -> Self:
        self._partial_payments.append(
            PartialPayment(
                amount=amount,
                payment_date=payment_date,
                payment_form=payment_form,
                other_payment_form=other_payment_form,
                payment_description=payment_description,
            )
        )
        return self

    def add_partial_payment_model(self, partial_payment: PartialPayment) -> Self:
        self._partial_payments.append(partial_payment)
        return self

    def clear_partial_payments(self) -> Self:
        self._partial_payments = []
        return self

    def to_bank_account(self, account_number: str, swift: str | None = None) -> Self:
        self._bank_accounts.append(
            BankAccount(account_number=account_number, swift=swift)
        )
        return self

    def add_bank_account_model(self, account: BankAccount) -> Self:
        self._bank_accounts.append(account)
        return self

    def clear_bank_accounts(self) -> Self:
        self._bank_accounts = []
        return self

    def to_factor_bank_account(
        self, account_number: str, swift: str | None = None
    ) -> Self:
        self._factor_bank_accounts.append(
            BankAccount(account_number=account_number, swift=swift)
        )
        return self

    def add_factor_bank_account_model(self, account: BankAccount) -> Self:
        self._factor_bank_accounts.append(account)
        return self

    def clear_factor_bank_accounts(self) -> Self:
        self._factor_bank_accounts = []
        return self

    def discount(self, *, terms: str | None = None, amount: str | None = None) -> Self:
        self._discount_terms = terms
        self._discount_amount = amount
        return self

    def payment_link(self, link: str | None) -> Self:
        self._payment_link = link
        return self

    def ipksef(self, value: str | None) -> Self:
        self._ipksef = value
        return self

    def done(self) -> TBuilder:
        payment = InvoicePayment(
            paid=self._paid,
            payment_date=self._payment_date,
            partial_payment_status=self._partial_payment_status,
            partial_payments=self._partial_payments,
            payment_terms=self._payment_terms,
            payment_form=self._payment_form,
            other_payment_form=self._other_payment_form,
            payment_description=self._payment_description,
            bank_accounts=self._bank_accounts,
            factor_bank_accounts=self._factor_bank_accounts,
            discount_terms=self._discount_terms,
            discount_amount=self._discount_amount,
            payment_link=self._payment_link,
            ipksef=self._ipksef,
        )

        if self._is_empty(payment):
            self.parent._payment = None
        else:
            self.parent._payment = payment
        return self.parent

    @staticmethod
    def _is_empty(payment: InvoicePayment) -> bool:
        return (
            not payment.paid
            and payment.payment_date is None
            and payment.partial_payment_status is None
            and not payment.partial_payments
            and not payment.payment_terms
            and payment.payment_form is None
            and not payment.other_payment_form
            and payment.payment_description is None
            and not payment.bank_accounts
            and not payment.factor_bank_accounts
            and payment.discount_terms is None
            and payment.discount_amount is None
            and payment.payment_link is None
            and payment.ipksef is None
        )


class AnnotationsBuilder(Generic[TBuilder]):
    def __init__(
        self, parent: TBuilder, existing_state: InvoiceAnnotationsContext | None = None
    ) -> None:
        self.parent = parent
        self.model(existing_state)

    def model(self, annotations: InvoiceAnnotationsContext | None) -> Self:
        annotations = (
            annotations.model_copy(deep=True) if annotations is not None else None
        )
        self._cash_accounting = annotations.cash_accounting if annotations else False
        self._self_billing = annotations.self_billing if annotations else False
        self._reverse_charge_annotation = (
            annotations.reverse_charge_annotation if annotations else False
        )
        self._split_payment = annotations.split_payment if annotations else False
        self._simplified_procedure = (
            annotations.simplified_procedure if annotations else False
        )
        self._margin_procedure = annotations.margin_procedure if annotations else None
        tax_exemption = annotations.tax_exemption if annotations else None
        self._tax_exemption_basis_act = (
            tax_exemption.legal_basis_act if tax_exemption else None
        )
        self._tax_exemption_basis_eu_directive = (
            tax_exemption.legal_basis_eu_directive if tax_exemption else None
        )
        self._tax_exemption_basis_other = (
            tax_exemption.legal_basis_other if tax_exemption else None
        )
        new_transport_supply = annotations.new_transport_supply if annotations else None
        self._article_42_5_required = (
            new_transport_supply.article_42_5_required if new_transport_supply else None
        )
        self._new_transport_items = (
            list(new_transport_supply.items) if new_transport_supply else []
        )
        return self

    def cash_accounting(self, enabled: bool = True) -> Self:
        self._cash_accounting = enabled
        return self

    def self_billing(self, enabled: bool = True) -> Self:
        self._self_billing = enabled
        return self

    def reverse_charge_annotation(self, enabled: bool = True) -> Self:
        self._reverse_charge_annotation = enabled
        return self

    def split_payment(self, enabled: bool = True) -> Self:
        self._split_payment = enabled
        return self

    def simplified_procedure(self, enabled: bool = True) -> Self:
        self._simplified_procedure = enabled
        return self

    def margin_procedure(self, procedure: MarginProcedure | str | None) -> Self:
        self._margin_procedure = (
            None
            if procedure is None
            else BaseFA3Builder._coerce_margin_procedure(procedure)
        )
        return self

    def tax_exemption(
        self,
        *,
        legal_basis_act: str | None = None,
        legal_basis_eu_directive: str | None = None,
        legal_basis_other: str | None = None,
    ) -> Self:
        self._tax_exemption_basis_act = legal_basis_act
        self._tax_exemption_basis_eu_directive = legal_basis_eu_directive
        self._tax_exemption_basis_other = legal_basis_other
        return self

    def clear_tax_exemption(self) -> Self:
        self._tax_exemption_basis_act = None
        self._tax_exemption_basis_eu_directive = None
        self._tax_exemption_basis_other = None
        return self

    def new_transport_supply(
        self, *, article_42_5_required: bool | None = None
    ) -> Self:
        self._article_42_5_required = article_42_5_required
        return self

    def add_new_transport_item(self, **kwargs: Any) -> Self:
        self._new_transport_items.append(NewTransportMeansItem(**kwargs))
        return self

    def add_new_transport_item_model(self, item: NewTransportMeansItem) -> Self:
        self._new_transport_items.append(item)
        return self

    def clear_new_transport_items(self) -> Self:
        self._new_transport_items = []
        self._article_42_5_required = None
        return self

    def done(self) -> TBuilder:
        tax_exemption = None
        if any(
            value is not None
            for value in (
                self._tax_exemption_basis_act,
                self._tax_exemption_basis_eu_directive,
                self._tax_exemption_basis_other,
            )
        ):
            tax_exemption = InvoiceTaxExemption(
                legal_basis_act=self._tax_exemption_basis_act,
                legal_basis_eu_directive=self._tax_exemption_basis_eu_directive,
                legal_basis_other=self._tax_exemption_basis_other,
            )

        new_transport_supply = None
        if self._new_transport_items or self._article_42_5_required is not None:
            new_transport_supply = NewTransportSupply(
                article_42_5_required=self._article_42_5_required,
                items=self._new_transport_items,
            )

        annotations = InvoiceAnnotationsContext(
            cash_accounting=self._cash_accounting,
            self_billing=self._self_billing,
            reverse_charge_annotation=self._reverse_charge_annotation,
            split_payment=self._split_payment,
            tax_exemption=tax_exemption,
            new_transport_supply=new_transport_supply,
            simplified_procedure=self._simplified_procedure,
            margin_procedure=self._margin_procedure,
        )

        if self._is_empty(annotations):
            self.parent._annotations = None
        else:
            self.parent._annotations = annotations
        return self.parent

    @staticmethod
    def _is_empty(annotations: InvoiceAnnotationsContext) -> bool:
        return (
            not annotations.cash_accounting
            and not annotations.self_billing
            and not annotations.reverse_charge_annotation
            and not annotations.split_payment
            and annotations.tax_exemption is None
            and annotations.new_transport_supply is None
            and not annotations.simplified_procedure
            and annotations.margin_procedure is None
        )


class CorrectionBuilder(Generic[TBuilder]):
    def __init__(
        self, parent: TBuilder, existing_state: CorrectionInvoiceContext | None = None
    ) -> None:
        self.parent = parent
        self.model(existing_state)

    def model(self, correction: CorrectionInvoiceContext | None) -> Self:
        correction = (
            correction.model_copy(deep=True) if correction is not None else None
        )
        self._correction_reason = correction.correction_reason if correction else None
        self._correction_effect_type = (
            correction.correction_effect_type if correction else None
        )
        self._corrected_invoices = (
            list(correction.corrected_invoices) if correction else []
        )
        self._corrected_invoice_period = (
            correction.corrected_invoice_period if correction else None
        )
        self._corrected_invoice_number_override = (
            correction.corrected_invoice_number_override if correction else None
        )
        self._corrected_seller = correction.corrected_seller if correction else None
        self._corrected_buyers = list(correction.corrected_buyers) if correction else []
        return self

    def for_reason(self, reason: str | None) -> Self:
        self._correction_reason = reason
        return self

    def effect_type(self, effect_type: CorrectionEffectType | None) -> Self:
        self._correction_effect_type = effect_type
        return self

    def add_corrected_invoice(
        self,
        *,
        issue_date: date,
        invoice_number: str,
        ksef_id: str | None = None,
        outside_ksef: bool = False,
    ) -> Self:
        self._corrected_invoices.append(
            CorrectedInvoiceReference(
                issue_date=issue_date,
                invoice_number=invoice_number,
                ksef_id=ksef_id,
                outside_ksef=outside_ksef,
            )
        )
        return self

    def add_corrected_invoice_model(
        self, corrected_invoice: CorrectedInvoiceReference
    ) -> Self:
        self._corrected_invoices.append(corrected_invoice)
        return self

    def clear_corrected_invoices(self) -> Self:
        self._corrected_invoices = []
        return self

    def corrected_invoice_period(self, value: str | None) -> Self:
        self._corrected_invoice_period = value
        return self

    def corrected_invoice_number_override(self, value: str | None) -> Self:
        self._corrected_invoice_number_override = value
        return self

    def corrected_seller(
        self,
        *,
        name: str,
        tax_id: str,
        country_code: str,
        address_line_1: str,
        address_line_2: str | None = None,
        gln: str | None = None,
        vat_prefix: str | None = None,
    ) -> Self:
        self._corrected_seller = CorrectedSellerEntity(
            vat_prefix=vat_prefix,
            tax_id=tax_id,
            name=name,
            address=BaseFA3Builder._build_address(
                country_code=country_code,
                address_line_1=address_line_1,
                address_line_2=address_line_2,
                gln=gln,
            ),
        )
        return self

    def corrected_seller_model(
        self, corrected_seller: CorrectedSellerEntity | None
    ) -> Self:
        self._corrected_seller = corrected_seller
        return self

    def add_corrected_buyer(
        self,
        *,
        name: str,
        tax_id: str | None = None,
        eu_vat_id: str | None = None,
        country_code: str | None = None,
        other_id: str | None = None,
        no_id: bool = False,
        address_line_1: str | None = None,
        address_line_2: str | None = None,
        gln: str | None = None,
        buyer_id: str | None = None,
    ) -> Self:
        address = None
        if country_code is not None and address_line_1 is not None:
            address = BaseFA3Builder._build_address(
                country_code=country_code,
                address_line_1=address_line_1,
                address_line_2=address_line_2,
                gln=gln,
            )
        self._corrected_buyers.append(
            CorrectedBuyerEntity(
                tax_id=tax_id,
                eu_vat_id=eu_vat_id,
                country_code=country_code,
                other_id=other_id,
                no_id=no_id,
                name=name,
                address=address,
                buyer_id=buyer_id,
            )
        )
        return self

    def add_corrected_buyer_model(self, corrected_buyer: CorrectedBuyerEntity) -> Self:
        self._corrected_buyers.append(corrected_buyer)
        return self

    def clear_corrected_buyers(self) -> Self:
        self._corrected_buyers = []
        return self

    def done(self) -> TBuilder:
        correction = CorrectionInvoiceContext(
            correction_reason=self._correction_reason,
            correction_effect_type=self._correction_effect_type,
            corrected_invoices=self._corrected_invoices,
            corrected_invoice_period=self._corrected_invoice_period,
            corrected_invoice_number_override=self._corrected_invoice_number_override,
            corrected_seller=self._corrected_seller,
            corrected_buyers=self._corrected_buyers,
        )

        if self._is_empty(correction):
            self.parent._correction = None
        else:
            self.parent._correction = correction
        return self.parent

    @staticmethod
    def _is_empty(correction: CorrectionInvoiceContext) -> bool:
        return (
            correction.correction_reason is None
            and correction.correction_effect_type is None
            and not correction.corrected_invoices
            and correction.corrected_invoice_period is None
            and correction.corrected_invoice_number_override is None
            and correction.corrected_seller is None
            and not correction.corrected_buyers
        )


class AdvanceBuilder(Generic[TAdvanceBuilder]):
    def __init__(
        self,
        parent: TAdvanceBuilder,
        existing_state: AdvancePaymentInvoiceContext | None = None,
    ) -> None:
        self.parent = parent
        self.model(existing_state)

    def model(self, advance: AdvancePaymentInvoiceContext | None) -> Self:
        advance = advance.model_copy(deep=True) if advance is not None else None
        self._amount_before_correction = (
            advance.amount_before_correction if advance else None
        )
        self._currency_exchange_rate_before_correction = (
            advance.currency_exchange_rate_before_correction if advance else None
        )
        self._advance_partial_payments = (
            list(advance.advance_partial_payments) if advance else []
        )
        self._advance_invoice_references = (
            list(advance.advance_invoice_references) if advance else []
        )
        return self

    def amount_before_correction(self, amount: Decimal | None) -> Self:
        self._amount_before_correction = amount
        return self

    def currency_exchange_rate_before_correction(
        self, exchange_rate: Decimal | None
    ) -> Self:
        self._currency_exchange_rate_before_correction = exchange_rate
        return self

    def add_partial_payment(
        self,
        *,
        payment_date: date,
        amount: Decimal,
        currency_exchange_rate: Decimal | None = None,
    ) -> Self:
        self._advance_partial_payments.append(
            PartialAdvancePayment(
                payment_date=payment_date,
                amount=amount,
                currency_exchange_rate=currency_exchange_rate,
            )
        )
        return self

    def add_partial_payment_model(self, partial_payment: PartialAdvancePayment) -> Self:
        self._advance_partial_payments.append(partial_payment)
        return self

    def clear_partial_payments(self) -> Self:
        self._advance_partial_payments = []
        return self

    def add_invoice_reference(
        self,
        *,
        ksef_id: str | None = None,
        invoice_number: str | None = None,
        outside_ksef: bool = False,
        deduction_amount: Decimal | None = None,
        deduction_reason: str | None = None,
    ) -> Self:
        self._advance_invoice_references.append(
            AdvanceInvoiceReference(
                ksef_id=ksef_id,
                invoice_number=invoice_number,
                outside_ksef=outside_ksef,
                deduction_amount=deduction_amount,
                deduction_reason=deduction_reason,
            )
        )
        return self

    def add_invoice_reference_model(
        self, invoice_reference: AdvanceInvoiceReference
    ) -> Self:
        self._advance_invoice_references.append(invoice_reference)
        return self

    def clear_invoice_references(self) -> Self:
        self._advance_invoice_references = []
        return self

    def done(self) -> TAdvanceBuilder:
        advance = AdvancePaymentInvoiceContext(
            amount_before_correction=self._amount_before_correction,
            currency_exchange_rate_before_correction=(
                self._currency_exchange_rate_before_correction
            ),
            advance_partial_payments=self._advance_partial_payments,
            advance_invoice_references=self._advance_invoice_references,
        )

        if self._is_empty(advance):
            self.parent._advance = None
        else:
            self.parent._advance = advance
        return self.parent

    @staticmethod
    def _is_empty(advance: AdvancePaymentInvoiceContext) -> bool:
        return (
            advance.amount_before_correction is None
            and advance.currency_exchange_rate_before_correction is None
            and not advance.advance_partial_payments
            and not advance.advance_invoice_references
        )


class SettlementBuilder(Generic[TSettlementBuilder]):
    def __init__(
        self,
        parent: TSettlementBuilder,
        existing_state: InvoiceSettlement | None = None,
    ) -> None:
        self.parent = parent
        self.model(existing_state)

    def model(self, settlement: InvoiceSettlement | None) -> Self:
        settlement = (
            settlement.model_copy(deep=True) if settlement is not None else None
        )
        self._charges = list(settlement.charges) if settlement else []
        self._charges_total = settlement.charges_total if settlement else None
        self._deductions = list(settlement.deductions) if settlement else []
        self._deductions_total = settlement.deductions_total if settlement else None
        self._amount_due = settlement.amount_due if settlement else None
        self._amount_to_settle = settlement.amount_to_settle if settlement else None
        return self

    def add_charge(self, *, amount: Decimal, reason: str) -> Self:
        self._charges.append(SettlementCharge(amount=amount, reason=reason))
        return self

    def add_charge_model(self, charge: SettlementCharge) -> Self:
        self._charges.append(charge)
        return self

    def clear_charges(self) -> Self:
        self._charges = []
        self._charges_total = None
        return self

    def charges_total(self, amount: Decimal | None) -> Self:
        self._charges_total = amount
        return self

    def add_deduction(self, *, amount: Decimal, reason: str) -> Self:
        self._deductions.append(SettlementDeduction(amount=amount, reason=reason))
        return self

    def add_deduction_model(self, deduction: SettlementDeduction) -> Self:
        self._deductions.append(deduction)
        return self

    def clear_deductions(self) -> Self:
        self._deductions = []
        self._deductions_total = None
        return self

    def deductions_total(self, amount: Decimal | None) -> Self:
        self._deductions_total = amount
        return self

    def amount_due(self, amount: Decimal | None) -> Self:
        self._amount_due = amount
        return self

    def amount_to_settle(self, amount: Decimal | None) -> Self:
        self._amount_to_settle = amount
        return self

    def done(self) -> TSettlementBuilder:
        settlement = InvoiceSettlement(
            charges=self._charges,
            charges_total=self._charges_total,
            deductions=self._deductions,
            deductions_total=self._deductions_total,
            amount_due=self._amount_due,
            amount_to_settle=self._amount_to_settle,
        )

        if self._is_empty(settlement):
            self.parent._settlement = None
        else:
            self.parent._settlement = settlement
        return self.parent

    @staticmethod
    def _is_empty(settlement: InvoiceSettlement) -> bool:
        return (
            not settlement.charges
            and settlement.charges_total in {None, Decimal("0.00")}
            and not settlement.deductions
            and settlement.deductions_total in {None, Decimal("0.00")}
            and settlement.amount_due is None
            and settlement.amount_to_settle is None
        )


class OrderBuilder(Generic[TOrderBuilder]):
    def __init__(
        self,
        parent: TOrderBuilder,
        existing_state: InvoiceOrder | None,
        declared_total: Decimal,
    ) -> None:
        self.parent = parent
        self._declared_total = declared_total
        self.model(existing_state)

    def model(self, order: InvoiceOrder | None) -> Self:
        order = order.model_copy(deep=True) if order is not None else None
        self._order_lines = list(order.order_lines) if order else []
        if order is not None and order.total_value is not None:
            self._declared_total = order.total_value
        return self

    def total_value(self, amount: Decimal) -> Self:
        self._declared_total = amount
        return self

    def add_line(
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
        vat_rate_value = BaseFA3Builder._coerce_vat_rate(vat_rate)
        line = AdvanceOrderLine(
            gross_amount=gross_amount,
            vat_rate=vat_rate_value.value if vat_rate_value is not None else None,
            name=name,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            unit_price_net=unit_price_net,
            sale_category=BaseFA3Builder._coerce_sale_category(sale_category).value,
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
        self._order_lines.append(line)
        return self

    def add_line_model(self, line: AdvanceOrderLine) -> Self:
        self._order_lines.append(line)
        return self

    def replace_lines(self, lines: Sequence[AdvanceOrderLine]) -> Self:
        self._order_lines = list(lines)
        return self

    def clear_lines(self) -> Self:
        self._order_lines = []
        return self

    def done(self) -> TOrderBuilder:
        self.parent._gross_advance_amount = self._declared_total
        if not self._order_lines:
            self.parent._order = None
            return self.parent

        self.parent._order = InvoiceOrder(
            total_value=self._declared_total,
            order_lines=self._order_lines,
        )
        return self.parent
