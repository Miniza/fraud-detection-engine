# Running Tests

## Installation

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

The test suite uses:

- **pytest** — Test framework
- **pytest-asyncio** — Async test support
- **pytest-cov** — Code coverage
- **httpx** — HTTP client for API testing
- **SQLite in-memory** — Fast test database

## Run All Tests

```bash
pytest tests/unit/ -v
```

## Run Specific Test File

```bash
pytest tests/unit/test_amount_rule.py
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures (test database, sample data)
├── README.md                # This file
└── unit/
    ├── __init__.py
    ├── test_amount_rule.py        # Amount rule boundary conditions
    ├── test_velocity_rule.py      # Velocity rule timing + count
    ├── test_blacklist_rule.py     # Blacklist cache + database
    ├── test_idempotency.py        # Idempotent decorator + deduplication
    ├── test_transaction_service.py # Service layer (CRUD)
    └── test_exceptions.py         # Exception handling + HTTP responses
```

## Test Coverage by Module

| Module                  | Tests | Coverage                               |
| ----------------------- | ----- | -------------------------------------- |
| **Amount Rule**         | 4     | Boundary conditions, threshold testing |
| **Velocity Rule**       | 4     | Time windows, transaction counting     |
| **Blacklist Rule**      | 4     | Cache usage, merchant lookup           |
| **Idempotency**         | 5     | Deduplication, multi-tx handling       |
| **Transaction Service** | 6     | CRUD, SNS publishing, alerts           |
| **Exception Handlers**  | 5     | Error codes, error messages            |

## Example Test Output

```
tests/unit/test_amount_rule.py::test_high_amount_flagged PASSED                 [8%]
tests/unit/test_amount_rule.py::test_low_amount_not_flagged PASSED              [17%]
tests/unit/test_amount_rule.py::test_amount_exactly_at_threshold PASSED         [25%]
tests/unit/test_amount_rule.py::test_amount_just_above_threshold PASSED         [33%]
tests/unit/test_velocity_rule.py::test_velocity_flagged_multiple_transactions PASSED [42%]
...

========================= 28 passed in 1.24s ==========================
```

## Test Database

Tests use an **in-memory SQLite database** for speed:

- Each test gets a fresh DB state
- No network calls to Postgres
- Runs in ~1-2 seconds total

The `conftest.py` provides fixtures:

- `test_db` — Fresh async session
- `sample_transaction` — Pre-populated transaction
- `sample_high_amount_transaction` — High-value transaction for amount rule
- `sample_blacklisted_merchant` — Blacklist entry
