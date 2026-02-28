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
    description: str | None = None
    amount: Decimal | None = None
    transaction_type: str | None = None  # 'income' or 'expense'
    payment_method: str | None = None   # see PaymentMethod enum
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
    r"\s+\d{2}:\d{2}"                         # time
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

        date_str, code, channel, amounts_str, description = m.groups()
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

        # Payment method: check description first (more specific), then channel
        combined = description + " " + channel
        payment_method = _detect_payment_method(combined) or _SCB_CHANNEL_TO_METHOD.get(channel.upper())

        parsed_date, date_conf = _parse_date(date_str)
        rows.append(ExtractedRow(
            raw_text=line,
            transaction_date=parsed_date,
            description=description,
            amount=amount,
            transaction_type=tx_type,
            payment_method=payment_method,
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
    r"(?:[ \t]+\d{2}:\d{2})?"            # optional time HH:MM
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

        date_str, description, amount_str, _balance, channel_memo = m.groups()
        description = description.strip()

        # Skip opening/closing balance rows
        if _KBANK_SKIP_RE.search(description):
            continue

        try:
            amount = Decimal(amount_str.replace(",", ""))
        except InvalidOperation:
            continue

        # Determine income/expense from Thai description
        if _KBANK_INCOME_RE.search(description):
            tx_type = "income"
        elif _KBANK_EXPENSE_RE.search(description):
            tx_type = "expense"
        else:
            continue  # unknown type — skip

        # Date is DD-MM-YY (hyphen) — convert to slash for _parse_date
        date_slash = date_str.replace("-", "/")
        parsed_date, date_conf = _parse_date(date_slash)

        # Payment method from channel/memo
        channel_text = (channel_memo or "") + " " + description
        payment_method = _detect_payment_method(channel_text)
        if payment_method is None and channel_memo:
            if _KBANK_CHANNEL_RE.search(channel_memo):
                payment_method = "bank_transfer"

        rows.append(ExtractedRow(
            raw_text=line,
            transaction_date=parsed_date,
            description=description,
            amount=amount,
            transaction_type=tx_type,
            payment_method=payment_method,
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
