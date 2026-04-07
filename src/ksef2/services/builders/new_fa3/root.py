from datetime import datetime
from typing import Self, override

from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from ksef2.domain.models.fa3 import Attachment, InvoiceFooter
from ksef2.domain.models.fa3.body.root import KsefInvoiceBody
from ksef2.domain.protocols import BaseBuilderProtocol
from ksef2.domain.models.fa3.header import InvoiceHeader
from ksef2.domain.models.fa3.invoice import KsefInvoice
from ksef2.domain.models.fa3.party import ContactInfo, InvoiceAddress, InvoiceEntity
from ksef2.domain.models.fa3.third_party import InvoiceThirdParty
from ksef2.infra.mappers.helpers import to_aware_datetime
from ksef2.infra.mappers.invoices.fa3.invoice import to_spec as invoice_to_spec
from ksef2.infra.schema.fa3.models.schemat import Faktura, __NAMESPACE__
from ksef2.services.builders.fa3.attachment import AttachmentBuilder
from ksef2.services.builders.fa3.footer import FooterBuilder
from ksef2.services.builders.new_fa3.body.standard import StandardBodyBuilder


class StandardInvoiceBuilder(BaseBuilderProtocol):
    def __init__(self) -> None:
        self._header: InvoiceHeader | None = InvoiceHeader()
        self._seller: InvoiceEntity | None = None
        self._buyer: InvoiceEntity | None = None
        self._third_parties: list[InvoiceThirdParty] | None = None
        self._body: KsefInvoiceBody | None = None
        self._footer: InvoiceFooter | None = None
        self._attachment: Attachment | None = None

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

    @override
    def header_model(self, header: InvoiceHeader) -> Self:
        self._header = header
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

    @override
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

    @override
    def buyer_model(self, buyer: InvoiceEntity) -> Self:
        self._buyer = buyer
        return self

    def footer(self) -> FooterBuilder:
        return FooterBuilder(self, existing_state=self._footer)

    @override
    def footer_model(self, footer: InvoiceFooter) -> Self:
        self._footer = footer
        return self

    def attachment(self) -> AttachmentBuilder:
        return AttachmentBuilder(self, existing_state=self._attachment)

    @override
    def attachment_model(self, attachment: Attachment) -> Self:
        self._attachment = attachment
        return self

    def standard(self) -> StandardBodyBuilder[Self]:
        return StandardBodyBuilder(self, self._set_body, self._body)

    def _set_body(self, body: KsefInvoiceBody) -> None:
        if self._body is not None:
            raise ValueError("Invoice body has already been set")
        self._body = body

    def build(self) -> KsefInvoice:
        if self._header is None:
            raise ValueError("Invoice header is required but not set.")
        if self._seller is None:
            raise ValueError("Invoice seller is required but not set.")
        if self._buyer is None:
            raise ValueError("Invoice buyer is required but not set.")
        if self._body is None:
            raise ValueError("Invoice body is required but not set.")

        if self._third_parties is None:
            self._third_parties = []

        return KsefInvoice(
            header=self._header,
            seller=self._seller,
            buyer=self._buyer,
            third_parties=self._third_parties,
            body=self._body,
            footer=self._footer,
            attachment=self._attachment,
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
        return serializer.render(  # pyright: ignore[reportUnknownMemberType]
            self.to_spec(), ns_map={None: __NAMESPACE__}
        )

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
        customer_number: str | None = None,
        jst_subordinate_unit: bool = False,
        vat_group_member: bool = False,
        email: str | None = None,
        phone: str | None = None,
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
            address=StandardInvoiceBuilder._build_address(
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
