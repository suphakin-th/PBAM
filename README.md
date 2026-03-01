# PBAM — Private Banking & Analytic Management

A personal finance tracker for Thai banking with PDF bank-statement import (OCR), money-flow visualization, and multi-currency support.

---

## Objective

**Problem** : Do you annoying about do a accountant or financial log every month for track all your spend??

it take MTF couple hour per day right? here it is i build it for my own,
who mtf want to use it for youself (Just personal and non-comercial) take it!!.

![DashBoard 1](data/pic/1.png)

![DashBoard 2](data/pic/2.png)


## Features

- **Money-flow tree** — income sources → bank accounts → expense categories, visualized as an interactive DAG (ReactFlow)
- **Transaction management** — CRUD with category assignment, tags, comments, and recurring-transaction flags
- **PDF import wizard** — upload a bank statement PDF, OCR extracts rows automatically, review/correct each row, confirm to commit to the ledger
- **Multi-currency** — all amounts stored in THB base; original amount + currency + exchange rate preserved for display
- **Category tree** — unlimited hierarchy, income/expense/transfer types, color + icon per node
- **Transaction groups** — manually group related transactions (e.g. a trip)
- **JWT auth** — username/password login, token revocation via jti hash

---

## Supported Bank Statement Formats

| Bank | Product | Format | Detection |
|------|---------|--------|-----------|
| Krungsri | T1 credit card (General Card) | `DD/MM/YY  ···24 spaces···  DD/MM/YY  DESC  [PRINCIPAL  NNN/NNN]  MONTHLY_DUE` | Issuer header + wide date gap |
| BAY / Kept | Kept savings account | `DD/MM/YYYY(BE)  HH:MM  DESCRIPTION  [DEBIT]  [CREDIT]  BALANCE  CHANNEL` | "Kept savings" / "ธนาคารกรุงศรีอยุธยา" header |
| KTC | Credit card (JCB / World) | `DD/MM/YY DD/MM/YY DESCRIPTION AMOUNT` | Two date columns with year, compact spacing |
| SCB | Credit card (UP2ME) | `DD/MM DD/MM DESCRIPTION AMOUNT` | Two date columns, no year |
| SCB | Savings / current account | `DD/MM/YY HH:MM X1/X2 CHANNEL … DESC: …` | X1=income, X2=expense channel codes |
| KBANK | Savings / current account | `DD-MM-YY [HH:MM] THAI_DESC AMOUNT BALANCE [CHANNEL]` | Thai income/expense keywords |
| Scanned PDFs | Any | EasyOCR fallback (returns empty when EasyOCR not installed) | — |

**BAY / Kept notes:**
- Dates are in Buddhist Era (BE) — year is converted automatically (e.g. 2569 → 2026).
- Multi-line descriptions are joined automatically.
- Internal savings-pocket movements (`ฝากเก็บเองไป`, `แอบเก็บอัตโนมัติไป`, and the corresponding return flows) are **skipped** — they are not real income or expense.
- Receipts from a Thai bank (`เงินเข้าจาก SCB/KBANK/…`) are imported as **transfer** type, not income, to prevent double-counting. Use the **Link transfer pair** button in the Transactions page to pair them with the matching outgoing transfer from your other account.
- Interest income (`รับโอนดอกเบี้ยจาก …`) is correctly imported as **income**.

**Payment method** is auto-detected from description keywords: PromptPay, QR code, Line Pay, TrueMoney, GrabPay, ATM, internet banking (K PLUS), subscriptions (Netflix / Spotify / YouTube), e-commerce (Shopee / Lazada / Amazon), Agoda, gaming (Hoyoverse / Steam), and more.

---

## Architecture

```
PBAM/
├── backend/          # FastAPI (Python 3.12, uv)
│   └── src/pbam/
│       ├── domain/           # Pure entities, value objects, repo protocols (no I/O)
│       │   ├── identity/     # User, Session
│       │   ├── finance/      # Account, Transaction, Category, Group, Money
│       │   └── document/     # OcrJob, StagingTransaction
│       ├── application/      # Use-case commands and queries (no framework imports)
│       │   ├── identity/
│       │   ├── finance/
│       │   └── document/
│       ├── infrastructure/   # SQLAlchemy, auth (JWT + Argon2id), OCR processor
│       │   ├── database/     # ORM models, concrete repos, Alembic migrations
│       │   ├── auth/         # jwt.py, password.py
│       │   └── ocr/          # processor.py (pdftotext + EasyOCR)
│       └── interfaces/       # Facade + FastAPI routers + Pydantic schemas
│           ├── facade.py     # PBAMFacade — single entry point for all use cases
│           └── api/v1/
│               ├── routers/  # auth, accounts, transactions, categories, groups, ocr
│               └── schemas/  # Pydantic v2 request/response models
└── frontend/         # React 18 + TypeScript + Ant Design 5 + Vite (pnpm)
    └── src/
        ├── domain/           # TypeScript interfaces mirroring backend domain
        ├── application/      # Zustand stores + hooks
        ├── infrastructure/   # Axios API clients
        └── presentation/
            ├── AppLayout.tsx # Sidebar navigation shell
            ├── facade/       # Bridges stores → UI props
            ├── components/   # FlowTree, TransactionTable, StagingReviewTable, …
            └── pages/        # Dashboard, Transactions, Categories, Import, Settings, Login
```

**Key design decisions:**

| Concern | Choice |
|---------|--------|
| DB | PostgreSQL 16, multi-schema (`identity`, `finance`, `document`, `audit`) |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Migrations | Alembic |
| Auth | JWT (`python-jose`) + Argon2id (`argon2-cffi`), jti hash revocation |
| OCR pipeline | `pdftotext -layout` (fast, accurate for machine-generated PDFs) → EasyOCR fallback for scanned PDFs |
| Flow tree | ReactFlow (node-based DAG viewer) |
| State | Zustand |
| HTTP client | Axios with JWT interceptor + 401 redirect |
| Validation | Pydantic v2 (backend), TypeScript strict mode (frontend) |
| Packages | uv (backend), pnpm (frontend) |

---

## Database Schema

### Bounded contexts (PostgreSQL schemas)

- **`identity`** — `users`, `user_sessions`
- **`finance`** — `accounts`, `transactions`, `transaction_categories`, `transaction_comments`, `transaction_groups`, `transaction_group_members`
- **`document`** — `ocr_jobs`, `staging_transactions`
- **`audit`** — `activity_log` (append-only trigger)

### Currency storage

```
amount_thb        NUMERIC(15,4)   -- base amount in THB (always present)
original_amount   NUMERIC(15,4)   -- original amount (NULL if THB)
original_currency VARCHAR(3)      -- ISO 4217 code (NULL if THB)
exchange_rate     NUMERIC(15,8)   -- rate at transaction time
```

### OCR staging flow

```
PDF upload
  └─▶ ocr_jobs row created (status=pending)
      └─▶ BackgroundTask runs OCR processor
          └─▶ staging_transactions rows inserted (status=review)
              └─▶ User reviews/corrects rows in UI
                  └─▶ POST /ocr/{id}/commit
                      └─▶ Non-discarded rows → finance.transactions
                          └─▶ ocr_jobs.status = committed
```

---

## Quick Start

### Prerequisites

- PostgreSQL 16 (local) **or** Docker / Podman for containerised setup
- Python 3.12+ with `uv` (`pip install uv`)
- Node.js 22+ with `pnpm` (`npm install -g pnpm`)
- `pdftotext` for machine-generated PDFs: `sudo apt install poppler-utils`
- (Optional) EasyOCR + pdf2image for scanned PDFs: `pip install easyocr pdf2image`

---

### Option A — Local development (no containers)

**1. Start PostgreSQL** (create the `pbam` DB and user if first time):

```bash
createuser -s pbam
createdb -O pbam pbam
# or in psql: CREATE USER pbam PASSWORD 'pbam_dev_password'; CREATE DATABASE pbam OWNER pbam;
```

**2. One-command start** — checks PostgreSQL, runs migrations, starts backend + frontend:

```bash
./start-dev.sh
```

| URL | Service |
|-----|---------|
| `http://localhost:5173` | Frontend (React) |
| `http://localhost:8000` | Backend API |
| `http://localhost:8000/docs` | Swagger / interactive API docs |

Press **Ctrl+C** to stop everything cleanly.

**Manual start** (individual terminals):

```bash
# Terminal 1 — backend
cd backend
PYTHONPATH=src python3 -m uvicorn pbam.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend
pnpm install   # first time only
pnpm dev
```

---

### Option B — Containers (Docker / Podman)

The project targets **Podman** on the reference dev machine (Podman 5.7.1).
Plain Docker and Docker Compose work identically.

Install `podman-compose` once if needed:

```bash
pip install podman-compose
```

**I already have PostgreSQL running locally** — just start backend + frontend containers:

```bash
~/.local/bin/podman-compose up -d
# or: docker compose up -d
```

The backend connects to your local PostgreSQL via `host.containers.internal:5432` automatically.

**I don't have local PostgreSQL** — use the full stack with a containerised DB:

```bash
~/.local/bin/podman-compose -f docker-compose.yml -f docker-compose.db.yml up -d
# or: docker compose -f docker-compose.yml -f docker-compose.db.yml up -d
```

Migrations run automatically inside the backend container on startup.

| URL | Service |
|-----|---------|
| `http://localhost:5173` | Frontend |
| `http://localhost:8000` | Backend API |
| `http://localhost:8000/docs` | API docs |

---

### Environment variables (backend)

Copy `.env.example` to `.env` and set:

```env
DATABASE_URL=postgresql+asyncpg://pbam:pbam_dev_password@localhost:5432/pbam
SECRET_KEY=<openssl rand -hex 32>
ENVIRONMENT=development
STORAGE_PATH=./storage
```

---

## API Reference

Base path: `/api/v1`

Interactive docs at `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`.

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account → returns JWT |
| POST | `/auth/login` | Login → returns JWT |
| POST | `/auth/logout` | Revoke current token |
| GET | `/auth/me` | Current user info |

### Accounts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/accounts` | List user accounts |
| POST | `/accounts` | Create account |
| PATCH | `/accounts/{id}` | Update name / metadata / active flag |
| DELETE | `/accounts/{id}` | Soft-delete account |

### Transactions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/transactions` | List with filters: `date_from`, `date_to`, `account_id`, `category_id`, `limit`, `offset` |
| POST | `/transactions` | Create transaction |
| PATCH | `/transactions/{id}` | Update description / category / payment method / tags / date |
| DELETE | `/transactions/{id}` | Soft-delete |
| GET | `/transactions/flow-tree` | Money flow DAG for date range |
| GET | `/transactions/{id}/comments` | List comments |
| POST | `/transactions/{id}/comments` | Add comment |
| DELETE | `/transactions/{id}/comments/{cid}` | Delete comment |

### Categories

| Method | Path | Description |
|--------|------|-------------|
| GET | `/categories` | Category tree (nested) |
| POST | `/categories` | Create category |
| PATCH | `/categories/{id}` | Update |
| DELETE | `/categories/{id}` | Soft-delete |

### Transaction Groups

| Method | Path | Description |
|--------|------|-------------|
| GET | `/groups` | List groups |
| POST | `/groups` | Create group |
| POST | `/groups/{id}/members/{tx_id}` | Add transaction to group |
| DELETE | `/groups/{id}/members/{tx_id}` | Remove from group |
| DELETE | `/groups/{id}` | Delete group |

### OCR Import

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ocr/upload` | Upload PDF → starts background OCR job |
| GET | `/ocr` | List OCR jobs |
| GET | `/ocr/{id}` | Job status |
| GET | `/ocr/{id}/staging` | Extracted rows for review |
| PATCH | `/ocr/{id}/staging/{row_id}` | Edit a staging row |
| DELETE | `/ocr/{id}/staging/{row_id}` | Discard a staging row |
| POST | `/ocr/{id}/commit` | Commit all non-discarded rows to transactions |

---

## Payment Methods

Auto-detected from transaction description text:

| Code | Means |
|------|-------|
| `credit_card` | Credit card purchase |
| `debit_card` | Debit card |
| `qr_code` | QR-code payment / QR merchants |
| `promptpay` | PromptPay phone/ID transfer |
| `bank_transfer` | Internet banking transfer (ENET, BCMS, K PLUS) |
| `digital_wallet` | Line Pay, TrueMoney, GrabPay |
| `atm` | ATM cash withdrawal |
| `cash` | Cash payment |
| `online` | Generic online / e-commerce |
| `subscription` | Recurring subscription (Netflix, Spotify, YouTube, etc.) |
| `unknown` | Fallback when no pattern matched |

---

## Development

### Backend

```bash
cd backend
uv sync
PYTHONPATH=src uv run uvicorn pbam.main:app --reload   # http://localhost:8000
uv run pytest                                          # run tests
uv run ruff check src                                  # lint
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:5173
pnpm type-check   # TypeScript strict check
pnpm build        # production build
```

### Alembic migrations

```bash
cd backend
# Create a new migration
uv run alembic revision --autogenerate -m "describe change"
# Apply
PYTHONPATH=src python3 -m alembic upgrade head
# Rollback one step
PYTHONPATH=src python3 -m alembic downgrade -1
```

---

## Security Notes

- Passwords hashed with **Argon2id** (memory-hard, resistant to GPU cracking)
- JWT tokens identified by a `jti` UUID; its SHA-256 hash is stored in `user_sessions` for revocation on logout
- All user-owned tables use PostgreSQL **Row Level Security** — the app role can only see rows matching the authenticated user's ID
- Financial records use **soft deletes** (`deleted_at`) — nothing is ever physically removed from the ledger
- Audit trail in `audit.activity_log` is INSERT-only; the app role has `REVOKE DELETE, UPDATE` on that table
- Bank account metadata stores only **masked data** (last 4 digits of account number)
- PDF files are stored on the server filesystem; the path is recorded in the DB but file content is never stored in DB columns

---

## Known Issues Fixed (UAT)

These bugs were found and fixed during initial UAT:

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Register succeeds but user not saved — login returns "Invalid credentials" | `get_db()` in `dependencies.py` used a raw SQLAlchemy session context that never committed the transaction | Changed to `get_db_session()` which commits on success and rolls back on exception |
| `POST /accounts` returns 500 — `TypeError: can't compare offset-naive and offset-aware datetimes` | `UserSession.is_active` compared `expires_at` (UTC-aware) against `datetime.utcnow()` (naive, no timezone) | Replaced all `datetime.utcnow()` calls with `datetime.now(timezone.utc)` in `domain/identity/entities.py` |
