"""OCR processor: PDF → images → EasyOCR → structured data."""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# Heavy deps — lazy loaded on first use so the module can be imported without them
try:
    import easyocr as _easyocr_module  # noqa: F401
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

try:
    from pdf2image import convert_from_bytes as _convert_from_bytes  # noqa: F401
    from PIL import Image as _Image  # noqa: F401
    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    _PDF2IMAGE_AVAILABLE = False


@dataclass
class ExtractedRow:
    """A single transaction row extracted from OCR output."""
    raw_text: str
    transaction_date: str | None = None  # ISO format YYYY-MM-DD if parsed
    transaction_time: str | None = None  # HH:MM extracted from PDF line (e.g. "16:25")
    description: str | None = None
    amount: Decimal | None = None
    transaction_type: str | None = None  # 'income', 'expense', or 'transfer'
    payment_method: str | None = None   # see PaymentMethod enum
    counterparty_ref: str | None = None  # bank code + masked account (e.g. "SCB X7290")
    counterparty_name: str | None = None # person or merchant name
    confidence: dict[str, float] = field(default_factory=dict)
    sort_order: int = 0


@dataclass
class OcrResult:
    raw_output: dict[str, Any]
    rows: list[ExtractedRow]
    page_count: int


_reader = None


def _get_reader():
    global _reader
    if not _EASYOCR_AVAILABLE:
        raise RuntimeError("easyocr is not installed. Install it with: pip install easyocr")
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["th", "en"], gpu=False)
    return _reader


def hash_file(content: bytes) -> str:
    """SHA-256 hex digest of file bytes."""
    return hashlib.sha256(content).hexdigest()


def pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> list:
    """Convert PDF bytes to a list of PIL images (one per page)."""
    if not _PDF2IMAGE_AVAILABLE:
        raise RuntimeError("pdf2image is not installed. Install it with: pip install pdf2image")
    from pdf2image import convert_from_bytes
    return convert_from_bytes(pdf_bytes, dpi=dpi)


def ocr_image(image) -> list[tuple[list, str, float]]:
    """Run EasyOCR on a PIL image. Returns list of (bbox, text, confidence)."""
    reader = _get_reader()
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    return reader.readtext(img_bytes.getvalue())


# ── Thai / international date patterns ──────────────────────────────────────
_DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    (re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b"), "%d/%m/%Y"),
    # YYYY-MM-DD
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "%Y-%m-%d"),
]

_AMOUNT_PATTERN = re.compile(r"[\d,]+\.\d{2}")
_NEGATIVE_INDICATORS = {"DR", "ถอน", "จ่าย", "debit", "withdraw"}
_POSITIVE_INDICATORS = {"CR", "ฝาก", "รับ", "credit", "deposit"}

# ── Shared: Thai bank code + transfer-direction keywords ─────────────────────
# Used by multiple parsers to upgrade 'expense'/'income' → 'transfer' when the
# description clearly shows money moving between two bank accounts.
_THAI_BANK_CODE_RE = re.compile(
    r"\b(SCB|KBANK|KBank|BBL|KTB|BAY|TMB|TTB|GSB|BAAC|GHB|KK|TISCO|LH"
    r"|CIMB|UOB|CITI|ICBC|TBANK|LHBANK|GHBANK|ISBT|TCRB"
    r"|Krungsri|กรุงศรี|กสิกร|ไทยพาณิชย์|กรุงไทย|กรุงเทพ|ทหารไทย)\b"
)
_TRANSFER_OUT_KW_RE = re.compile(r"โอนไป|โอนออก|โอนเงินไป", re.I)
_TRANSFER_IN_KW_RE = re.compile(r"โอนมาจาก|รับโอนจาก|รับเงินจาก", re.I)

# ── Credit card bill payment detection ───────────────────────────────────────
# When a savings/current account pays a credit card bill, the debit shows up as
# an outgoing payment on the savings statement.  These are transfers between own
# accounts, NOT expenses — the real expenses were already recorded when the card
# was swiped.  Match the Thai "เพื่อชำระ … CARD/บัตร" pattern plus common
# credit card issuer names.
_CREDIT_CARD_PAYMENT_RE = re.compile(
    r"เพื่อชำระ.*(CARD|KTC|KRUNGTHAI|GENERAL\s*CARD|Krungsri|AYUDHYA|บัตรเครดิต|บัตร\s*เครดิต)"
    r"|ชำระบัตรเครดิต"
    r"|credit\s*card\s*payment"
    r"|ชำระ\s*(KTC|KRUNGTHAI|GENERAL|Krungsri|SCB\s*CARD|KBANK\s*CARD|BAY\s*CARD)\b"
    # SCB "จ่ายบิล" (bill payment) to credit card / loan issuers
    r"|จ่ายบิล\s+.*(CARD|KTC|KRUNGTHAI|AYUDHYA|CardX|credit|บัตร)",
    re.I,
)

# Investment/securities account transfers (savings → brokerage/fund) = not expense
_INVESTMENT_TRANSFER_RE = re.compile(
    r"Transfer\s+to\s+SCB.*(Securities|หลักทรัพย์|Webull|Invest)"
    r"|DDR\s+(บริษัทหลักทรัพย์|Securities|อินโนเวสท์|InnovestX)",
    re.I,
)

# ── Credit card: payment RECEIVED detection ───────────────────────────────────
# On a credit card statement a negative row = credit = money coming IN.
# Most of these are the cardholder paying their own bill from a debit account
# — they should be 'transfer', not 'income'.
# Matches the standard "Payment-BANK(code)Channel" format used by Thai credit
# card issuers (KTC, SCB Visa, Krungsri) plus plain "Payment received".
_CC_PAYMENT_RECEIVED_RE = re.compile(
    r"Payment[-\s]*(KBANK|SCB|BAY|BBL|KTB|TMB|TTB|Krungsri|PromptPay|\d{3})"
    r"|\bpayment\s+received\b"
    r"|ขอบคุณสำหรับยอดชำระ"    # "Thank you for payment" — Krungsri style
    r"|ยอดชำระจากบัญชี",          # "payment from account"
    re.I,
)

# ── Counterparty extraction ───────────────────────────────────────────────────
# Matches a bank code + optional masked account ref (e.g. "SCB X7290", "BAY x4497")
# then captures any trailing text as the person/merchant name.
_COUNTERPARTY_EXTRACT_RE = re.compile(
    r"(SCB|KBANK|KBank|BBL|KTB|BAY|TMB|TTB|GSB|BAAC|GHB|KK|TISCO|LH"
    r"|CIMB|UOB|CITI|ICBC|TBANK|LHBANK|GHBANK|Krungsri|กรุงศรี|กสิกร"
    r"|ไทยพาณิชย์|กรุงไทย|กรุงเทพ|ทหารไทย)"
    r"(?:\s+([Xx]\d{3,}|\d{4,}))?"  # optional: masked account ref "X7290" / "x4497"
    r"[ \t]*(.*?)$",
    re.I,
)


def _extract_counterparty(description: str) -> tuple[str | None, str | None]:
    """Return (counterparty_ref, counterparty_name) from a transaction description.

    counterparty_ref  — bank code + optional masked number, e.g. "SCB X7290", "BAY x4497"
    counterparty_name — person or merchant name that follows, e.g. "นาย สุภกิณห์ ธิวงค์"
    """
    m = _COUNTERPARTY_EXTRACT_RE.search(description)
    if not m:
        return None, None
    bank = m.group(1)
    acct = (m.group(2) or "").strip()
    name = (m.group(3) or "").strip()
    ref = f"{bank} {acct}".strip() if acct else bank
    return ref, name or None


# Payment method detection patterns (checked in order, first match wins)
# Format: (pattern, payment_method_value)
_PAYMENT_METHOD_PATTERNS: list[tuple[re.Pattern, str]] = [
    # PromptPay (พร้อมเพย์) — Thai inter-bank transfer via ID/phone
    (re.compile(r"promptpay|พรอมเพย|พร้อมเพย์", re.I), "promptpay"),
    # QR Code payments (QR- prefix in merchant name, or QR bill payment desc)
    (re.compile(r"\bQR[-*]|qr\s*code|qr\s*payment|scan\s*qr|สแกน\s*qr|จ่ายบิล\s*qr|จ่ายบิล\s*bt", re.I), "qr_code"),
    # Line Pay / Line Man
    (re.compile(r"linepay|line\s*pay|line\s*man|liff", re.I), "digital_wallet"),
    # GrabPay
    (re.compile(r"grabpay|grab\.com|grab\s*food|grab\s*express", re.I), "digital_wallet"),
    # TrueMoney wallet top-up or payment
    (re.compile(r"truemoney|true\s*money|tmn|เติมเงิน\s*[tw]|true\s*digital", re.I), "digital_wallet"),
    # Shopee / ShopeePay / ShopeeFood
    (re.compile(r"shopeepay|shopeefood|shopeeth|shopee", re.I), "digital_wallet"),
    # Lazada Wallet
    (re.compile(r"lazada", re.I), "digital_wallet"),
    # Netflix, Spotify, Apple, Google subscriptions
    (re.compile(r"netflix|spotify|apple\.com/bill|apple\s*tv|google\s*play|google\s*one|google\s*x\b|google\s*youtube|youtube\s*premium|amazon\s*prime", re.I), "subscription"),
    # Amazon Marketplace purchases (AMZ_SD / AMZ A_SD formats)
    (re.compile(r"amz[_\s]*(?:a[_\s]*)?sd|amazon[_\s]com|amzn\.com", re.I), "online"),
    # Hoyoverse, Steam, gaming
    (re.compile(r"hoyoverse|steamgames|steam\s*games|playstation|nintendo|blizzard|riot\s*games", re.I), "online"),
    # Online travel booking
    (re.compile(r"agoda\.com|agoda\b|booking\.com|airbnb|expedia", re.I), "online"),
    # OMISE — Thai online payment gateway (ticketing, events)
    (re.compile(r"omise\s*\*", re.I), "online"),
    # ATM withdrawal
    (re.compile(r"\batm\b|ถอนเงน|ถอนเงิน", re.I), "atm"),
    # Internet / mobile banking transfer or bill payment
    (re.compile(r"internet\s*banking|web\s*bank|mobile\s*bank|ibk|payment[-\s]*(internet|scb|kbank|bbl|ktb|bay)|payment\s*received|k\s*plus|k-cash", re.I), "bank_transfer"),
    # International online (foreign merchant URL or currency indicator)
    (re.compile(r"\b(USD|EUR|GBP|JPY|SGD|CNY|HKD|AUD)\b.*[0-9]|\.(com|co\.jp|co\.uk|sg|au|th)\b|https?://", re.I), "online"),
]


def _detect_payment_method(text: str) -> str | None:
    """Detect payment method from transaction description. Returns method key or None."""
    for pattern, method in _PAYMENT_METHOD_PATTERNS:
        if pattern.search(text):
            return method
    return None


def _parse_date(text: str) -> tuple[str | None, float]:
    """Attempt to parse a date string. Returns (ISO date string | None, confidence)."""
    for pattern, _ in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 3:
                    d, mo, y = groups
                    if len(y) == 2:
                        # ≤30 → CE 20xx (e.g. "26" → 2026); >30 → Thai BE 25xx (e.g. "68" → 2568)
                        y = ("20" + y) if int(y) <= 30 else ("25" + y)
                    # Handle Thai Buddhist Era (BE is CE + 543)
                    year_int = int(y)
                    if year_int > 2500:
                        year_int -= 543
                    parsed = date(year_int, int(mo), int(d))
                    return parsed.isoformat(), 0.85
            except (ValueError, TypeError):
                continue
    return None, 0.0


def _parse_amount(text: str) -> tuple[Decimal | None, float]:
    """Extract the largest numeric amount from text."""
    matches = _AMOUNT_PATTERN.findall(text)
    if not matches:
        return None, 0.0
    # Take the last/largest match (usually the transaction amount in bank statements)
    raw = max(matches, key=lambda x: float(x.replace(",", "")))
    try:
        return Decimal(raw.replace(",", "")), 0.80
    except InvalidOperation:
        return None, 0.0


def _infer_transaction_type(text: str) -> tuple[str | None, float]:
    upper = text.upper()
    for indicator in _NEGATIVE_INDICATORS:
        if indicator.upper() in upper:
            return "expense", 0.75
    for indicator in _POSITIVE_INDICATORS:
        if indicator.upper() in upper:
            return "income", 0.75
    return None, 0.0


def _extract_text_via_pdftotext(pdf_bytes: bytes) -> list[str] | None:
    """Try to extract text using pdftotext (fast, machine-generated PDFs).
    Returns list of lines, or None if pdftotext is unavailable."""
    import os
    import subprocess
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = f.name
        result = subprocess.run(
            ["pdftotext", "-layout", tmp_path, "-"],
            capture_output=True, text=True, timeout=30,
        )
        os.unlink(tmp_path)
        if result.returncode == 0:
            return result.stdout.splitlines()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _parse_pdftotext_lines(lines: list[str]) -> list[ExtractedRow]:
    """Parse transaction rows from pdftotext output.

    Supports two Thai credit card statement formats:

    SCB (no year in transaction lines):
      12/01  11/01  DESCRIPTION  411.00

    KTC (DD/MM/YY for both dates):
      26/01/26  26/01/26  Payment-SCB(014)Internet  - 7,152.95

    Negative amounts (credit / payment received) use soft-hyphen U+00AD or '-'.
    """
    rows: list[ExtractedRow] = []
    sort_order = 0

    # KTC: TRANS_DATE(DD/MM/YY)  POSTING_DATE(DD/MM/YY)  DESCRIPTION  AMOUNT
    _ktc = re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4})"         # trans date (with year)
        r"\s+(\d{1,2}/\d{1,2}/\d{2,4})"        # posting date (with year)
        r"\s+(.+?)\s+"                          # description (lazy)
        r"([\u00ad\-]?\s*[\d,]+\.\d{2})\s*$"   # amount
    )

    # SCB: POSTING_DATE(DD/MM)  [TRANS_DATE(DD/MM)]  DESCRIPTION  AMOUNT
    _scb = re.compile(
        r"^(\d{1,2}/\d{1,2})"                  # posting date (no year)
        r"(?:\s+(\d{1,2}/\d{1,2}))?"           # optional trans date (no year)
        r"\s+(.+?)\s+"                          # description (lazy)
        r"([\u00ad\-]?\s*[\d,]+\.\d{2})\s*$"   # amount
    )

    for line in lines:
        line = line.strip()
        if not line:
            continue

        m = _ktc.match(line)
        if m:
            tx_date_str, _posting, description, amount_str = m.groups()
            date_str = tx_date_str  # already has year
        else:
            m = _scb.match(line)
            if not m:
                continue
            posting_date_str, tx_date_str, description, amount_str = m.groups()
            date_str = (tx_date_str or posting_date_str) + "/2026"  # append CE year

        is_negative = "\u00ad" in amount_str or amount_str.strip().startswith("-")
        clean_amount = re.sub(r"[\u00ad\-\s]", "", amount_str).replace(",", "")
        try:
            amount = Decimal(clean_amount)
        except InvalidOperation:
            continue

        parsed_date, date_conf = _parse_date(date_str)
        payment_method = _detect_payment_method(description)
        tx_type = "income" if is_negative else "expense"

        # On a credit card statement a negative (income) row that looks like
        # a bill payment = the cardholder paid from their debit account → transfer.
        if tx_type == "income" and _CC_PAYMENT_RECEIVED_RE.search(description):
            tx_type = "transfer"

        rows.append(ExtractedRow(
            raw_text=line,
            transaction_date=parsed_date,
            description=description.strip(),
            amount=amount,
            transaction_type=tx_type,
            payment_method=payment_method,
            confidence={
                "amount": 0.95,
                "date": date_conf,
                "transaction_type": 0.70,
                "description": 0.90,
                "payment_method": 0.75 if payment_method else 0.0,
            },
            sort_order=sort_order,
        ))
        sort_order += 1

    return rows


# ── Krungsri T1 Credit Card Statement (General Card Services) ───────────────────
# Format (after strip): DD/MM/YY  <10+ spaces>  DD/MM/YY  <spaces>  DESCRIPTION  <spaces>  AMOUNT
# The wide inter-date gap (24 chars) distinguishes this from KTC (2-3 spaces).
# Installment rows also carry the remaining principal before the monthly-due amount:
#   19/11/25  ...  15/02/26  CPP ON CALL  ...  19,737.33  ...  003/006  ...  5,026.70
# We use date 2 (billing date) as the transaction date.
_KRUSRI_TRAN_PATTERN = re.compile(
    r"^(\d{2}/\d{2}/\d{2})"     # date 1 – purchase date
    r"\s{10,}"                    # 10+ spaces  (Krungsri-wide layout)
    r"(\d{2}/\d{2}/\d{2})"      # date 2 – billing/posting date
    r"\s{3,}"                    # separator
    r"(.+?)"                     # description (lazy)
    r"\s{3,}"                    # whitespace before amount section
    r"(-?[\d,]+\.\d{2})\s*$"    # rightmost amount (monthly installment or fee)
)
# Installment fraction like "003/006" — extract for description annotation
_KRUSRI_INSTALLMENT_RE = re.compile(r"\b(\d{3}/\d{3})\b")
# Lines to skip (payment confirmations and subtotals are transfers/summaries)
_KRUSRI_SKIP_RE = re.compile(
    r"ขอบคณสำหรับยอดชำระ"   # "Thank you for payment" — credit card repayment
    r"|SUBTOTAL"
    r"|ยอดรวม"
    r"|คงวดตอเดอน"            # "remaining installment = ..."
)
# Detect Krungsri format by issuer name in header
_KRUSRI_HEADER_RE = re.compile(r"เจเนอรัล\s*คาร์ด|General\s*Card\s*Services", re.I)


def _parse_krusri_lines(lines: list[str]) -> list[ExtractedRow]:
    """Parse Krungsri T1 credit card statement (General Card Services).

    Two-date columnar format with 24-space gap between dates.
    Installment rows: date1  date2  DESCRIPTION  PRINCIPAL  INST_NO  MONTHLY_DUE
    Fee rows:        date1  date2  DESCRIPTION  AMOUNT
    Payment rows (negative) are skipped — they are credit card repayments.
    """
    # Require issuer header to avoid false positives on other formats
    header = "\n".join(lines[:30])
    if not _KRUSRI_HEADER_RE.search(header):
        return []

    rows: list[ExtractedRow] = []
    sort_order = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = _KRUSRI_TRAN_PATTERN.match(line)
        if not m:
            continue

        _date1, date2_str, desc_raw, amount_str = m.groups()

        # Skip payment/summary rows by description keyword
        if _KRUSRI_SKIP_RE.search(desc_raw):
            continue

        # Parse amount — negative = repayment, skip
        clean = amount_str.replace(",", "").replace("\u00ad", "-")
        try:
            amount = Decimal(clean)
        except InvalidOperation:
            continue
        if amount <= 0:
            continue

        # Clean description: for installment rows extract the "NNN/NNN" fraction
        # and strip the principal amount that gets captured in the lazy desc group
        desc = desc_raw.strip()
        inst_m = _KRUSRI_INSTALLMENT_RE.search(desc)
        if inst_m:
            fraction = inst_m.group(1)
            # Strip trailing: everything from the first amount-like number onward
            desc = re.sub(r"\s+[\d,]+\.\d{2}.*", "", desc).strip()
            desc = f"{desc} ({fraction})"
        else:
            # Remove any stray trailing numbers that leaked into the lazy group
            desc = re.sub(r"\s+[\d,]+\.\d{2}\s*$", "", desc).strip()

        # Use billing date (date 2) — installment rows have purchase date months ago
        parsed_date, date_conf = _parse_date(date2_str)
        payment_method = _detect_payment_method(desc) or "credit_card"

        rows.append(ExtractedRow(
            raw_text=line,
            transaction_date=parsed_date,
            description=desc,
            amount=amount,
            transaction_type="expense",
            payment_method=payment_method,
            confidence={
                "amount": 0.95,
                "date": date_conf,
                "transaction_type": 0.90,
                "description": 0.85,
                "payment_method": 0.80,
            },
            sort_order=sort_order,
        ))
        sort_order += 1

    return rows


# ── SCB Savings/Current Account Transaction Statement ──────────────────────────
# Format: DD/MM/YY HH:MM X1/X2 CHANNEL [DEBIT] [CREDIT] BALANCE DESC: description
# X1=credit/income, X2=debit/expense
_SCB_TRAN_PATTERN = re.compile(
    r"^(\d{2}/\d{2}/\d{2})"                  # date DD/MM/YY
    r"\s+(\d{2}:\d{2})"                       # time HH:MM (captured from PDF)
    r"\s+(X[12])"                             # code (X1=income, X2=expense)
    r"\s+([A-Z]+)"                            # channel (ENET, ATM, BCMS, SIPI)
    r"(.*)"                                   # amounts section
    r"DESC\s*:\s*(.*)$"                       # description after DESC:
)
_SCB_CHANNEL_TO_METHOD = {
    "ENET": "bank_transfer",   # internet/net banking
    "ATM": "atm",
    "BCMS": "bank_transfer",   # bank credit/direct deposit
    "SIPI": "promptpay",       # SIPI = PromptPay-based payment
    "KIOS": "atm",             # kiosk
}


def _parse_scb_tran_lines(lines: list[str]) -> list[ExtractedRow]:
    """Parse SCB savings/current account statement.

    Format per line:
      01/02/26 11:15 X2 ENET  65.00  496.55  DESC: จ่ายบิล QR
    X1 = credit (income), X2 = debit (expense).
    Two amounts before DESC: — first is transaction, second is running balance.
    """
    rows: list[ExtractedRow] = []
    sort_order = 0
    _amounts_re = re.compile(r"[\d,]+\.\d{2}")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = _SCB_TRAN_PATTERN.match(line)
        if not m:
            continue

        date_str, time_str, code, channel, amounts_str, description = m.groups()
        amounts = _amounts_re.findall(amounts_str)
        if not amounts:
            continue

        # First amount = transaction, last amount = running balance (skip)
        try:
            amount = Decimal(amounts[0].replace(",", ""))
        except InvalidOperation:
            continue

        tx_type = "income" if code == "X1" else "expense"
        description = description.strip()

        # Override: credit card bill / loan payment (savings → card/loan) = transfer
        if tx_type == "expense" and _CREDIT_CARD_PAYMENT_RE.search(description):
            tx_type = "transfer"

        # Override: investment/securities account top-up = transfer
        if tx_type == "expense" and _INVESTMENT_TRANSFER_RE.search(description):
            tx_type = "transfer"

        # Override: inter-bank transfer keywords + bank code → 'transfer'
        if tx_type != "transfer" and _THAI_BANK_CODE_RE.search(description):
            if tx_type == "expense" and _TRANSFER_OUT_KW_RE.search(description):
                tx_type = "transfer"
            elif tx_type == "income" and _TRANSFER_IN_KW_RE.search(description):
                tx_type = "transfer"

        # Payment method: check description first (more specific), then channel
        combined = description + " " + channel
        payment_method = _detect_payment_method(combined) or _SCB_CHANNEL_TO_METHOD.get(channel.upper())
        cp_ref, cp_name = _extract_counterparty(description)

        parsed_date, date_conf = _parse_date(date_str)
        rows.append(ExtractedRow(
            raw_text=line,
            transaction_date=parsed_date,
            transaction_time=time_str.strip(),
            description=description,
            amount=amount,
            transaction_type=tx_type,
            payment_method=payment_method,
            counterparty_ref=cp_ref,
            counterparty_name=cp_name,
            confidence={
                "amount": 0.95,
                "date": date_conf,
                "transaction_type": 0.90,  # X1/X2 is reliable
                "description": 0.85,
                "payment_method": 0.80 if payment_method else 0.0,
            },
            sort_order=sort_order,
        ))
        sort_order += 1

    return rows


# ── KBANK Savings/Current Account Transaction Statement ─────────────────────────
# Format: DD-MM-YY [HH:MM] THAI_DESCRIPTION  AMOUNT  BALANCE  CHANNEL  MEMO
_KBANK_TRAN_PATTERN = re.compile(
    r"^(\d{2}-\d{2}-\d{2})"              # date DD-MM-YY
    r"(?:[ \t]+(\d{2}:\d{2}))?"          # optional time HH:MM (captured from PDF)
    r"[ \t]+(.+?)[ \t]{3,}"              # description (lazy, ends at 3+ spaces)
    r"([\d,]+\.\d{2})"                   # transaction amount
    r"[ \t]+([\d,]+\.\d{2})"             # running balance
    r"(?:[ \t]+(.+?))?[ \t]*$"           # optional: channel + memo
)
# Thai terms that indicate income vs expense
_KBANK_INCOME_RE = re.compile(r"รับโอน|ฝากเงิน|รับเงิน|ดอกเบี้ย|รับโอนเงิน")
_KBANK_EXPENSE_RE = re.compile(r"ชำระเงิน|โอนเงิน|ถอนเงิน|หักเงิน|จ่ายเงิน")
_KBANK_SKIP_RE = re.compile(r"ยอดยกมา|ยอดยกไป|Balance Brought")  # opening balance rows
_KBANK_CHANNEL_RE = re.compile(r"K PLUS|K-Cash|Internet/Mobile|ATM KBANK|K BIZ", re.I)


def _parse_kbank_lines(lines: list[str]) -> list[ExtractedRow]:
    """Parse KBANK savings/current account statement.

    Format per line:
      03-01-26 16:25 รับโอนเงิน  5,000.00  5,000.00  K PLUS  จาก...
    Thai description determines income vs expense.
    """
    rows: list[ExtractedRow] = []
    sort_order = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = _KBANK_TRAN_PATTERN.match(line)
        if not m:
            continue

        date_str, time_str, description, amount_str, _balance, channel_memo = m.groups()
        description = description.strip()
        channel_memo = (channel_memo or "").strip()

        # Skip opening/closing balance rows
        if _KBANK_SKIP_RE.search(description):
            continue

        try:
            amount = Decimal(amount_str.replace(",", ""))
        except InvalidOperation:
            continue

        # Enrich description: strip the leading channel tag (K PLUS, K-Cash, etc.)
        # from channel_memo and append whatever remains (counterparty / company name).
        # e.g. "K PLUS  จาก SCB X7290 นาย สุภกิณห์ ธิวงค์" → append "จาก SCB X7290 นาย..."
        #      "pacificcrosshealth" → append as-is (no channel tag)
        ch_tag_m = _KBANK_CHANNEL_RE.match(channel_memo)
        memo_suffix = channel_memo[ch_tag_m.end():].strip() if ch_tag_m else channel_memo
        full_description = f"{description} {memo_suffix}".strip() if memo_suffix else description

        # Determine income/expense from Thai description (use full enriched text)
        if _KBANK_INCOME_RE.search(full_description):
            tx_type = "income"
        elif _KBANK_EXPENSE_RE.search(full_description):
            tx_type = "expense"
        else:
            continue  # unknown type — skip

        # Override: credit card bill / loan payment (savings → card/loan) = transfer
        if tx_type == "expense" and _CREDIT_CARD_PAYMENT_RE.search(full_description):
            tx_type = "transfer"

        # Override: investment/securities account top-up = transfer
        if tx_type == "expense" and _INVESTMENT_TRANSFER_RE.search(full_description):
            tx_type = "transfer"

        # Override: inter-bank transfer keywords + bank code → 'transfer'
        if tx_type != "transfer" and _THAI_BANK_CODE_RE.search(full_description):
            if tx_type == "expense" and re.search(r"โอนเงิน|โอนออก|โอนไป", full_description):
                tx_type = "transfer"
            elif tx_type == "income" and re.search(r"รับโอน|รับเงิน", full_description):
                tx_type = "transfer"

        # Date is DD-MM-YY (hyphen) — convert to slash for _parse_date
        date_slash = date_str.replace("-", "/")
        parsed_date, date_conf = _parse_date(date_slash)

        # Payment method from channel/memo
        channel_text = channel_memo + " " + full_description
        payment_method = _detect_payment_method(channel_text)
        if payment_method is None and channel_memo:
            if _KBANK_CHANNEL_RE.search(channel_memo):
                payment_method = "bank_transfer"

        cp_ref, cp_name = _extract_counterparty(full_description)

        rows.append(ExtractedRow(
            raw_text=line,
            transaction_date=parsed_date,
            transaction_time=time_str.strip() if time_str else None,
            description=full_description,
            amount=amount,
            transaction_type=tx_type,
            payment_method=payment_method,
            counterparty_ref=cp_ref,
            counterparty_name=cp_name,
            confidence={
                "amount": 0.95,
                "date": date_conf,
                "transaction_type": 0.90,
                "description": 0.80,
                "payment_method": 0.75 if payment_method else 0.0,
            },
            sort_order=sort_order,
        ))
        sort_order += 1

    return rows


# ── BAY (Kept by Krungsri) Savings Account Statement ─────────────────────────
# Format: DD/MM/YYYY(BE)  HH:MM  DESCRIPTION   [DEBIT_AMT]   [CREDIT_AMT]   BALANCE   CHANNEL
# Buddhist Era dates: year > 2500 → subtract 543 for CE year.
# Two-column layout: debit amount OR credit amount appears, the other is blank.
# Multi-line: description can continue on the next line(s) with no date prefix.
# Internal savings-pocket transfers (ฝากเก็บเองไป / แอบเก็บอัตโนมัติไป and the
# corresponding return flows "เงินเข้าจาก Grow/Fun savings") are skipped.
# Inter-bank receipts "เงินเข้าจาก [BANK_CODE]" are marked as *transfer* to avoid
# inflating income totals — the user links them as transfer pairs in the UI.
_BAY_HEADER_RE = re.compile(
    r"Kept\s+by\s+krungsri|ธนาคารกรุงศรีอยุธยา|Kept\s+savings|keptbykrungsri",
    re.I,
)
_BAY_DATE_LINE_RE = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+(.+)$")
_BAY_AMOUNT_RE = re.compile(r"[\d,]+\.\d{2}")
_BAY_CHANNEL_RE = re.compile(
    r"\b(Kept|OTH\.Mobile|OTH\.ATM|OTH\.Internet|OTH\.Counter|OTH\.CDM"
    r"|System|KMA|KOL|KBOL|KS\s+ATM|E-PAYMENT|BILL\s+PAYMENT|POS|EDC"
    r"|Branch|VISA|TELE\s+BANKING)\s*$",
    re.I,
)
# Lines to ignore: headers, footers, page breaks, summary rows
_BAY_IGNORE_LINE_RE = re.compile(
    r"Previous\s+balance|Ending\s+balance"
    r"|รวมรายการ|สิ้นสุดข้อมูล|End\s+of\s+statement"
    r"|Kept\s+by\s+krungsri|ธนาคารกรุงศรีอยุธยา|keptbykrungsri"
    r"|Page\s+\d+/\s*\d+|คำอธิบายช่องทาง|Channel\s+description"
    r"|วันที่\s+เวลา|Date\s+Time|Withdrawal|Deposit|Balance\s+\(THB\)"
    r"|Digital\s+account|ประเภทบัญชี|Account\s+type|รายการเดินบัญชี"
    r"|e-Statement|Period|รอบระหว่าง|ข้อมูล\s+ณ\s+วันที่|Date\s+as\s+of"
    r"|Kept\s+help\s+center|Bank\s+of\s+Ayudhya|เลขที่บัญชี|Reference\s+no"
    r"|ถอน/โอนออก|ฝาก/โอนเข้า|คงเหลือ|ช่องทาง"
    # Page-header data values that appear as right-aligned standalone lines
    r"|^Kept\s+savings$"          # account type value
    r"|^\d{3}-\d-\d{5}-\d"        # account number (000-7-71449-7)
    r"|Total\s+(withdrawal|deposit)"
    r"|รายการ\s*$",               # bare column header word
    re.I | re.MULTILINE,
)
# Internal savings-pocket operations → skip entirely
_BAY_INTERNAL_RE = re.compile(r"ฝากเก็บเองไป|แอบเก็บอัตโนมัติไป")
# Transfer *from* a savings pocket back to main → skip (just reversal of above)
_BAY_FROM_POCKET_RE = re.compile(r"^เงินเข้าจาก\s+\w+\s+savings\b", re.I)
# Thai bank codes — receipt from these → transaction_type = 'transfer'
_BAY_BANK_CODE_RE = re.compile(
    r"\b(SCB|KBANK|KBank|BBL|KTB|BAY|TMB|TTB|GSB|BAAC|GHB|KK|TISCO|LH"
    r"|CIMB|UOB|CITI|ICBC|TBANK|LHBANK|GHBANK|ISBT|TCRB)\b"
)
# Description keyword → transaction type
_BAY_INCOME_RE = re.compile(r"รับโอนดอกเบี้ย|รับดอกเบี้ย")          # interest income
_BAY_TRANSFER_IN_RE = re.compile(r"^เงินเข้าจาก\b")                   # money received
_BAY_TRANSFER_OUT_RE = re.compile(r"^เงินออกไป\b")                     # outgoing transfer
_BAY_EXPENSE_RE = re.compile(r"จ่ายด้วย|ชำระ")                        # QR/payment
_BAY_CHANNEL_TO_METHOD: dict[str, str] = {
    "kept": "digital_wallet",
    "oth.mobile": "bank_transfer",
    "oth.atm": "atm",
    "oth.internet": "bank_transfer",
    "oth.counter": "bank_transfer",
    "oth.cdm": "bank_transfer",
    "system": "bank_transfer",
    "kma": "bank_transfer",
    "kol": "bank_transfer",
    "kbol": "bank_transfer",
    "ks atm": "atm",
}


def _parse_bay_lines(lines: list[str]) -> list[ExtractedRow]:
    """Parse Kept by Krungsri (Bank of Ayudhya) savings account e-Statement.

    Columnar format with Buddhist Era (BE) dates — year >2500, subtract 543 for CE.
    Each transaction's amounts live on the *first* line; subsequent lines add
    description continuation only.  Internal savings-pocket movements are skipped.
    Inter-bank receipts ('เงินเข้าจาก SCB/KBANK/…') are typed as 'transfer' so that
    they do not inflate income totals before the user links the transfer pair.
    """
    header = "\n".join(lines[:40])
    if not _BAY_HEADER_RE.search(header):
        return []

    rows: list[ExtractedRow] = []
    sort_order = 0
    pending: dict | None = None   # {date_str, first_line, extra: list[str]}

    def flush() -> None:
        nonlocal pending, sort_order
        if pending is None:
            return
        entry, pending = pending, None

        first_line: str = entry["first_line"]
        extra: list[str] = entry["extra"]

        # All amounts live on the first line; last = running balance, first = tx
        amounts = _BAY_AMOUNT_RE.findall(first_line)
        if len(amounts) < 2:
            return  # balance-only row or header artefact

        try:
            tx_amount = Decimal(amounts[0].replace(",", ""))
        except InvalidOperation:
            return

        # Description = everything before the first amount on the first line
        first_amt_match = _BAY_AMOUNT_RE.search(first_line)
        desc_first = first_line[:first_amt_match.start()].strip() if first_amt_match else first_line.strip()

        # Channel = last token on the first line (after all amounts)
        ch_m = _BAY_CHANNEL_RE.search(first_line)
        channel = ch_m.group(1).strip() if ch_m else None

        # Join continuation lines into the description
        extra_text = " ".join(s.strip() for s in extra if s.strip())
        description = (desc_first + (" " + extra_text if extra_text else "")).strip()

        # Skip internal savings-pocket operations
        if _BAY_INTERNAL_RE.search(description):
            return
        if _BAY_FROM_POCKET_RE.search(description):
            return

        # Determine transaction type
        if _BAY_INCOME_RE.search(description):
            tx_type = "income"
        elif _BAY_TRANSFER_IN_RE.search(description):
            # "เงินเข้าจาก [source]" — treat as transfer when source is a bank code,
            # otherwise as income (salary / peer payment from a person).
            tx_type = "transfer" if _BAY_BANK_CODE_RE.search(description) else "income"
        elif _BAY_TRANSFER_OUT_RE.search(description):
            tx_type = "transfer"
        elif _BAY_EXPENSE_RE.search(description):
            tx_type = "expense"
        else:
            return  # unknown — skip

        # Override: credit card bill / loan payment (savings → card/loan) = transfer
        if tx_type == "expense" and _CREDIT_CARD_PAYMENT_RE.search(description):
            tx_type = "transfer"

        # Override: investment/securities account top-up = transfer
        if tx_type == "expense" and _INVESTMENT_TRANSFER_RE.search(description):
            tx_type = "transfer"

        parsed_date, date_conf = _parse_date(entry["date_str"])

        # Payment method: description keywords take priority, then channel mapping
        payment_method = _detect_payment_method(description)
        if payment_method is None:
            if re.search(r"จ่ายด้วย\s*QR", description, re.I):
                payment_method = "qr_code"
            elif channel:
                payment_method = _BAY_CHANNEL_TO_METHOD.get(channel.lower())

        cp_ref, cp_name = _extract_counterparty(description)

        rows.append(ExtractedRow(
            raw_text=first_line,
            transaction_date=parsed_date,
            transaction_time=entry.get("time_str"),
            description=description,
            amount=tx_amount,
            transaction_type=tx_type,
            payment_method=payment_method,
            counterparty_ref=cp_ref,
            counterparty_name=cp_name,
            confidence={
                "amount": 0.95,
                "date": date_conf,
                "transaction_type": 0.90,
                "description": 0.85,
                "payment_method": 0.70 if payment_method else 0.0,
            },
            sort_order=sort_order,
        ))
        sort_order += 1

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _BAY_IGNORE_LINE_RE.search(stripped):
            continue

        m = _BAY_DATE_LINE_RE.match(stripped)
        if m:
            flush()
            date_str, time_str, rest = m.groups()
            pending = {"date_str": date_str, "time_str": time_str, "first_line": rest, "extra": []}
        elif pending is not None:
            # Skip purely numeric lines (stray totals/balances) and bare date-range
            # lines that appear in page headers (e.g. "01/01/2569 - 01/03/2569")
            is_numeric_only = re.match(r"^[\d,.\s]+$", stripped)
            is_date_range = re.match(r"^\d{2}/\d{2}/\d{4}\s+-\s+\d{2}/\d{2}/\d{4}$", stripped)
            if not is_numeric_only and not is_date_range:
                pending["extra"].append(stripped)

    flush()
    return rows


def process_pdf(pdf_bytes: bytes) -> OcrResult:
    """Full pipeline: PDF bytes → OcrResult with extracted rows.

    Strategy:
    1. pdftotext (fast, accurate for machine-generated PDFs) — tries all known
       Thai bank statement formats in order until one produces rows.
    2. EasyOCR fallback — for scanned/image PDFs
    """
    # Strategy 1: pdftotext — try all parsers in order (first with rows wins)
    _PARSERS = [
        ("krusri",   _parse_krusri_lines),       # Krungsri T1 credit card (General Card Services)
        ("bay",      _parse_bay_lines),           # BAY / Kept by Krungsri savings account (BE dates)
        ("cc",       _parse_pdftotext_lines),    # KTC/SCB credit card (DD/MM or DD/MM/YY)
        ("scb_tran", _parse_scb_tran_lines),     # SCB savings/current account (X1/X2 channel)
        ("kbank",    _parse_kbank_lines),         # KBANK savings/current account (Thai desc)
    ]
    text_lines = _extract_text_via_pdftotext(pdf_bytes)
    if text_lines:
        for fmt, parser in _PARSERS:
            rows = parser(text_lines)
            if rows:
                return OcrResult(
                    raw_output={"source": "pdftotext", "format": fmt, "lines": len(text_lines)},
                    rows=rows,
                    page_count=1,
                )

    # Strategy 2: EasyOCR fallback (scanned/image PDFs)
    if not _EASYOCR_AVAILABLE or not _PDF2IMAGE_AVAILABLE:
        # Return empty result — no text extracted, OCR unavailable
        return OcrResult(
            raw_output={"source": "none", "reason": "scanned PDF and EasyOCR not installed"},
            rows=[],
            page_count=0,
        )
    try:
        images = pdf_to_images(pdf_bytes)
    except Exception:
        # PDF is corrupt, encrypted, or has a non-standard structure that
        # pdf2image/poppler cannot parse — return empty result instead of crashing.
        return OcrResult(
            raw_output={"source": "none", "reason": "pdf2image could not parse this PDF"},
            rows=[],
            page_count=0,
        )
    all_detections: list[dict] = []
    rows = []
    sort_order = 0

    for page_idx, image in enumerate(images):
        detections = ocr_image(image)
        for bbox, text, conf in detections:
            all_detections.append({"page": page_idx, "bbox": bbox, "text": text, "confidence": conf})
            amount, amount_conf = _parse_amount(text)
            if amount is None:
                continue
            parsed_date, date_conf = _parse_date(text)
            tx_type, type_conf = _infer_transaction_type(text)
            payment_method = _detect_payment_method(text)
            rows.append(ExtractedRow(
                raw_text=text,
                transaction_date=parsed_date,
                description=text.strip(),
                amount=amount,
                transaction_type=tx_type,
                payment_method=payment_method,
                confidence={
                    "amount": amount_conf * conf,
                    "date": date_conf * conf if parsed_date else 0.0,
                    "transaction_type": type_conf,
                    "description": conf,
                    "payment_method": 0.7 if payment_method else 0.0,
                },
                sort_order=sort_order,
            ))
            sort_order += 1

    return OcrResult(
        raw_output={"source": "easyocr", "detections": all_detections},
        rows=rows,
        page_count=len(images),
    )
