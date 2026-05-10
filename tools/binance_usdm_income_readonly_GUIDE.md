# Binance USD-M Income Readonly v1

## Purpose

Use this tool to query recent Binance USD-M Futures account income:

- `COMMISSION`: fee amount
- `FUNDING_FEE`: funding fee amount

This tool does not query funding rate percentage.

## Forbidden

- Do not modify `.env`.
- Do not print full `.env`.
- Do not output API key, API secret, signature, headers, or signed URL.
- Do not run `main.py run`, `main.py backfill`, or `main.py validate`.
- Do not write PostgreSQL.
- Do not call Binance `POST`, `PUT`, or `DELETE`.
- Do not place real account amounts in final response or project `HANDOFF.md`.

## API Key

Default variables:

- `API_KEY`
- `API_SECRET`

Override names:

```bash
python3 tools/binance_usdm_income_readonly.py --api-key-var API_KEY --api-secret-var API_SECRET
```

Use another env file:

```bash
python3 tools/binance_usdm_income_readonly.py --env-file /tmp/fake.env
```

## Dry Run

Dry-run is default.

```bash
python3 tools/binance_usdm_income_readonly.py --days 10
```

Expected:

```text
WILL_SEND_BINANCE_REQUEST: NO
```

## Fake Env Verification

```bash
python3 tools/binance_usdm_income_readonly.py --env-file /tmp/fake.env --days 10 --overwrite
```

Do not use `--execute` for fake env verification.

## Execute Read-Only

```bash
python3 tools/binance_usdm_income_readonly.py --days 10 --execute --confirm-readonly
```

Only these endpoints are allowed:

- `GET /fapi/v1/time`
- `GET /fapi/v1/income`

## Report Fields

Report is written under `tools/outputs/` and includes:

- run timestamp
- mode
- `WILL_SEND_BINANCE_REQUEST`
- base URL label
- days
- start / end time
- request count
- status
- `COMMISSION` by asset
- `FUNDING_FEE` by asset
- by symbol summary
- grand total by asset

## Overwrite

Existing reports are not overwritten unless `--overwrite` is passed.

## Partial / Blocked

- `partial`: pagination limit was reached; shorten `--days`.
- `blocked`: a safety rule stopped execution.

## Funding Fee

`FUNDING_FEE` is funding fee amount, not funding rate percentage.

## Asset Totals

Different assets are not added together.
