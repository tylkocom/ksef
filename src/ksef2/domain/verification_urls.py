"""Build KSeF invoice and certificate verification URLs (KOD I / KOD II).

The KSeF system defines two QR-code URL schemes for invoice verification:

* **KOD I** — online invoice verification URL.  Constructed from the seller
  NIP, the invoice issue date, and the SHA-256 hash of the invoice file (all
  data that is known locally, no API call required).

* **KOD II** — offline certificate verification URL.  Requires cryptographic
  signing with the issuer's private key and is *not* implemented here.

Reference: https://github.com/CIRFMF/ksef-docs/blob/main/kody-qr.md
"""

from datetime import date, datetime

from ksef2.config import Environment

_ONLINE_PATH_TEMPLATE = "/invoice/{nip}/{issue_date}/{invoice_hash}"


def _base64_to_base64url(value: str) -> str:
    """Convert a standard Base64 string to Base64URL encoding.

    Replaces ``+`` with ``-``, ``/`` with ``_`` and strips ``=`` padding
    as per RFC 4648 §5.
    """
    return value.replace("+", "-").replace("/", "_").rstrip("=")


def build_invoice_verification_url(
    *,
    environment: Environment,
    seller_nip: str,
    issue_date: date | datetime,
    invoice_hash_base64: str,
) -> str:
    """Build a KOD I invoice verification URL for an online invoice.

    When opened in a browser this URL shows a simplified presentation of the
    invoice's basic data and confirms its presence in KSeF.

    Args:
        environment: Target KSeF environment (its ``qr_base_url`` property
            provides the correct QR portal base URL).
        seller_nip: NIP of the seller (``P_1`` / ``Podmiot1`` on the invoice).
        issue_date: Invoice issue date (field ``P_1``).  Time information is
            ignored — only the date portion is used.
        invoice_hash_base64: SHA-256 hash of the invoice file encoded as
            **standard Base64** (the format returned by the KSeF API in
            ``invoiceHash``).  It is automatically converted to Base64URL
            as required by the KSeF QR specification.

    Returns:
        The full verification URL as a string.

    Example::

        from ksef2.config import Environment
        from ksef2.domain.verification_urls import build_invoice_verification_url

        url = build_invoice_verification_url(
            environment=Environment.TEST,
            seller_nip="1111111111",
            issue_date=date(2026, 2, 1),
            invoice_hash_base64="UtQp9Gpc51y+u3xApZjIjgkpZ01js+J8KflSPW8WzIE=",
        )
        # https://qr-test.ksef.mf.gov.pl/invoice/1111111111/01-02-2026/UtQp9Gpc51y-u3xApZjIjgkpZ01js-J8KflSPW8WzIE
    """
    date_obj = issue_date.date() if isinstance(issue_date, datetime) else issue_date
    date_str = date_obj.strftime("%d-%m-%Y")
    hash_b64url = _base64_to_base64url(invoice_hash_base64)

    path = _ONLINE_PATH_TEMPLATE.format(
        nip=seller_nip,
        issue_date=date_str,
        invoice_hash=hash_b64url,
    )
    return f"{environment.qr_base_url}{path}"
