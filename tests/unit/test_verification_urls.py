"""Tests for ksef2.domain.verification_urls module."""

from datetime import date, datetime

import pytest

from ksef2.config import Environment
from ksef2.domain.verification_urls import (
    _base64_to_base64url,  # pyright: ignore[reportPrivateUsage]
    build_invoice_verification_url,
)


class TestBase64ToBase64url:
    """Conversion from standard Base64 to Base64URL."""

    def test_replaces_plus_with_dash(self) -> None:
        assert _base64_to_base64url("a+b") == "a-b"

    def test_replaces_slash_with_underscore(self) -> None:
        assert _base64_to_base64url("a/b") == "a_b"

    def test_strips_equals_padding(self) -> None:
        assert _base64_to_base64url("abc==") == "abc"

    def test_combined(self) -> None:
        # The example hash from KSeF docs:
        # Standard Base64: UtQp9Gpc51y+u3xApZjIjgkpZ01js+J8KflSPW8WzIE=
        # Base64URL:       UtQp9Gpc51y-u3xApZjIjgkpZ01js-J8KflSPW8WzIE
        assert (
            _base64_to_base64url("UtQp9Gpc51y+u3xApZjIjgkpZ01js+J8KflSPW8WzIE=")
            == "UtQp9Gpc51y-u3xApZjIjgkpZ01js-J8KflSPW8WzIE"
        )

    def test_no_change_for_already_base64url(self) -> None:
        assert _base64_to_base64url("abcABC123_-") == "abcABC123_-"


class TestBuildInvoiceVerificationUrl:
    """KOD I invoice verification URL construction."""

    def test_test_environment_url(self) -> None:
        """Verify against the official example from KSeF docs."""
        url = build_invoice_verification_url(
            environment=Environment.TEST,
            seller_nip="1111111111",
            issue_date=date(2026, 2, 1),
            invoice_hash_base64="UtQp9Gpc51y+u3xApZjIjgkpZ01js+J8KflSPW8WzIE=",
        )
        assert url == (
            "https://qr-test.ksef.mf.gov.pl/invoice/1111111111/"
            "01-02-2026/UtQp9Gpc51y-u3xApZjIjgkpZ01js-J8KflSPW8WzIE"
        )

    def test_production_environment_url(self) -> None:
        url = build_invoice_verification_url(
            environment=Environment.PRODUCTION,
            seller_nip="1234567890",
            issue_date=date(2025, 12, 31),
            invoice_hash_base64="abcdefg+h/ijk==",
        )
        assert url.startswith("https://qr.ksef.mf.gov.pl/invoice/")
        assert "1234567890" in url
        assert "31-12-2025" in url
        assert "abcdefg-h_ijk" in url

    def test_demo_environment_url(self) -> None:
        url = build_invoice_verification_url(
            environment=Environment.DEMO,
            seller_nip="9999999999",
            issue_date=date(2026, 1, 15),
            invoice_hash_base64="AA==",
        )
        assert url.startswith("https://qr-demo.ksef.mf.gov.pl/invoice/")

    def test_accepts_datetime_issue_date(self) -> None:
        url = build_invoice_verification_url(
            environment=Environment.TEST,
            seller_nip="1111111111",
            issue_date=datetime(2026, 2, 1, 14, 30, 0),
            invoice_hash_base64="UtQp9Gpc51y+u3xApZjIjgkpZ01js+J8KflSPW8WzIE=",
        )
        # Time portion is ignored — only the date part is used.
        assert "01-02-2026" in url

    def test_hash_without_padding_already_base64url(self) -> None:
        url = build_invoice_verification_url(
            environment=Environment.TEST,
            seller_nip="1111111111",
            issue_date=date(2026, 2, 1),
            invoice_hash_base64="UtQp9Gpc51y-u3xApZjIjgkpZ01js-J8KflSPW8WzIE",
        )
        assert "UtQp9Gpc51y-u3xApZjIjgkpZ01js-J8KflSPW8WzIE" in url


class TestEnvironmentQrBaseUrl:
    """Environment.qr_base_url property."""

    def test_production(self) -> None:
        assert Environment.PRODUCTION.qr_base_url == "https://qr.ksef.mf.gov.pl"

    def test_test(self) -> None:
        assert Environment.TEST.qr_base_url == "https://qr-test.ksef.mf.gov.pl"

    def test_demo(self) -> None:
        assert Environment.DEMO.qr_base_url == "https://qr-demo.ksef.mf.gov.pl"
