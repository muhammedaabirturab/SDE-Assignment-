# Expense Sharing Service

A backend service for splitting shared expenses inside groups of friends: record who paid what,
see who owes whom, and settle up with the fewest possible payments.
Built for the **Decentro SDE Intern assignment - Expense Sharing Service**.

**Stack:** Python 3.11 - FastAPI - PostgreSQL - SQLAlchemy 2 - Alembic - Pydantic - Pytest - Docker

---

## 1. Project overview

Friends on a trip pay for different things. The service lets a group register users, create groups,
add members, record expenses (equal split by default), list the expense history and compute balances.
On top of the required features it adds **Smart Settlement** (mandatory product enhancement) and, as
optional bonuses, **recorded repayments**, **unequal splits**, **unit tests** and **Docker support**.

## 2. Problem statement

> Mohit, Rahul and Ankit go on a trip. Mohit pays Rs 1200 for dinner, shared equally. Each share is
> Rs 400, so Rahul owes Mohit Rs 400 and Ankit owes Mohit Rs 400.

The system must compute this from stored data (never hardcoded), for any number of expenses, payers
and groups.

## 3. Objectives

Correct money arithmetic - a normalised, constraint-heavy database design - clean layered code -
meaningful automated tests - documentation that describes only what is actually implemented.

## 4. Features

| Area | Status |
|---|---|
| Users: create, list | Implemented |
| Groups: create, add member, list members (no duplicate membership) | Implemented |
| Expenses: create with atomic equal split, list per group | Implemented |
| Balances: pairwise "who owes whom", overall or per group | Implemented |
| **Product enhancement: Smart Settlement suggestions** | Implemented |
| Bonus - Balance settlement (recorded repayments, history) | Implemented |
| Bonus - Unequal expense split (and equal split among a subset) | Implemented |
| Bonus - Automated tests | Implemented (446 tests) |
| Bonus - Docker / Docker Compose | Implemented |
| Postman collection / demo video (optional in the assignment) | Not provided - use Swagger UI at `/docs` |

## 5. Technology stack

Python 3.11, FastAPI 0.162, Uvicorn, PostgreSQL 16, SQLAlchemy 2.1 (ORM), Psycopg 3, Alembic,
Pydantic 2 / pydantic-settings, Pytest (+ `httpx2` for the TestClient), Docker + Docker Compose.
All versions are pinned in [`requirements.txt`](requirements.txt).

## 6. Architecture overview

Layered: **routes** (HTTP only) -> **services** (business rules, transactions) -> **models**
(SQLAlchemy + constraints) -> PostgreSQL. Pure algorithms (`split_equally`, `pairwise_debts`,
`compute_settlement_plan`) have no I/O and are unit-tested directly. Full diagram, request flow,
error strategy and concurrency notes: [docs/architecture.md](docs/architecture.md).

```mermaid
flowchart LR
    C([Client]) --> R[Routes<br/>app/api/routes]
    R --> S[Services<br/>app/services]
    S --> M[Models<br/>app/models]
    M --> DB[(PostgreSQL)]
    S --> U[Utils<br/>money, db]
    A[Alembic] --> DB
```

## 7. Project directory structure

```
.
├── app/
│   ├── main.py                  # app factory, routers, /health
│   ├── core/                    # config.py (env settings), exceptions.py (error handling)
│   ├── database/                # base.py (metadata, naming convention), connection.py (engine/session)
│   ├── models/                  # user, group, group_member, expense, expense_split, settlement
│   ├── schemas/                 # Pydantic request/response models
│   ├── api/routes/              # users, groups, expenses, balances, settlements
│   ├── services/                # user, group, expense, balance, settlement services
│   └── utils/                   # money.py (paise maths, equal split), db.py (commit_or_raise)
├── alembic/                     # env.py + versions/0001_initial_schema.py
├── tests/                       # users, groups, expenses, balances, settlements, money, migrations
├── docs/                        # architecture.md, database_schema.md, api_documentation.md
├── Dockerfile  docker-compose.yml  .dockerignore
├── alembic.ini  pytest.ini  requirements.txt
└── .env.example  .gitignore  README.md
```

## 8. Database schema

Six tables; full column-level documentation in [docs/database_schema.md](docs/database_schema.md).

| Table | Purpose | Key constraints |
|---|---|---|
| `users` | people | PK; unique `lower(name)` |
| `groups` | expense groups | PK |
| `group_members` | user <-> group | `UNIQUE(group_id, user_id)`, FKs |
| `expenses` | a payment by one member | `CHECK amount_paise > 0`; composite FK (payer is a member) |
| `expense_splits` | each participant's share, frozen at creation | `UNIQUE(expense_id, user_id)`, `CHECK share_paise >= 0`; composite FKs (same group, participant is a member) |
| `settlements` | real repayments (history) | `CHECK amount_paise > 0`, `CHECK paid_by <> paid_to`; composite FKs |

Notable choices:

* **Money is integer paise** (`BIGINT`), never float.
* **`expense_splits` stores the real allocation** at the moment the expense is created. A member who
  joins later is not charged for older expenses, and balances never depend on current membership.
* **Composite foreign keys** make "payer / participant must belong to the group" a *database* rule, in
  addition to the application checks.

## 9. Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ GROUP_MEMBERS : joins
    GROUPS ||--o{ GROUP_MEMBERS : has
    GROUPS ||--o{ EXPENSES : contains
    USERS ||--o{ EXPENSES : "pays"
    EXPENSES ||--|{ EXPENSE_SPLITS : "split into"
    USERS ||--o{ EXPENSE_SPLITS : "owes share"
    GROUPS ||--o{ SETTLEMENTS : records
    USERS ||--o{ SETTLEMENTS : "pays / receives"

    USERS { int id PK
            varchar name
            timestamptz created_at }
    GROUPS { int id PK
             varchar name
             timestamptz created_at }
    GROUP_MEMBERS { int id PK
                    int group_id FK
                    int user_id FK
                    timestamptz joined_at }
    EXPENSES { int id PK
               int group_id FK
               int paid_by FK
               bigint amount_paise
               varchar description
               timestamptz created_at }
    EXPENSE_SPLITS { int id PK
                     int expense_id FK
                     int group_id FK
                     int user_id FK
                     bigint share_paise }
    SETTLEMENTS { int id PK
                  int group_id FK
                  int paid_by FK
                  int paid_to FK
                  bigint amount_paise
                  varchar note
                  timestamptz created_at }
```

## 10. API documentation

Swagger UI: **http://localhost:8000/docs** (OpenAPI JSON at `/openapi.json`). Full reference with
request/response examples: [docs/api_documentation.md](docs/api_documentation.md).

| Method & path | Purpose |
|---|---|
| `POST /users`, `GET /users` | create / list users |
| `POST /groups` | create a group |
| `POST /groups/{group_id}/members`, `GET /groups/{group_id}/members` | add / list members |
| `POST /expenses` | record an expense (equal split by default) |
| `GET /groups/{group_id}/expenses` | expense history of a group |
| `GET /balances[?group_id=]` | who owes whom |
| `GET /groups/{group_id}/settlements/suggestions` | smart settlement plan |
| `POST /settlements`, `GET /groups/{group_id}/settlements` | record / list real repayments |
| `GET /health` | liveness and database check |

All the endpoints suggested by the assignment keep their suggested paths. Errors share one shape,
`{"error": {"code", "message", "details"}}`, with 404 (not found), 409 (duplicate), 422 (validation or
business rule) and a generic 500 that never leaks internals.

## 11. API request and response examples

```bash
curl -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"name": "Mohit"}'
# {"id":1,"name":"Mohit","created_at":"..."}

curl -X POST localhost:8000/expenses -H 'Content-Type: application/json' \
  -d '{"group_id":1,"paid_by":1,"amount":1200,"description":"Dinner"}'
# 201 -> splits: Mohit 400, Rahul 400, Ankit 400

curl localhost:8000/balances
# {"Rahul":{"owes":{"Mohit":400}},"Ankit":{"owes":{"Mohit":400}}}
```

Unequal split request body (bonus):

```json
{"group_id": 1, "paid_by": 1, "amount": 1000, "description": "Villa",
 "splits": [{"user_id": 1, "amount": 500}, {"user_id": 2, "amount": 300}, {"user_id": 3, "amount": 200}]}
```

## 12. Expense calculation methodology

1. Validate: group exists, payer exists and is a member, `amount > 0` with at most 2 decimals.
2. Convert rupees (`Decimal`) to **integer paise**.
3. Choose participants: all current group members by default (the payer is one of them and gets their own share row),
   or the explicit `participants`, or the explicit `splits`.
4. **Equal split:** `base = total // n`, `remainder = total % n`; the `remainder` leftover paise are
   given one each to the lowest user ids. Shares therefore always add up *exactly* to the total
   (100 over 3 people -> 33.34 / 33.33 / 33.33) and nothing is lost to rounding.
5. **Custom split:** every user must be a member, no duplicates, each amount > 0, sum must equal the total.
6. Insert the expense and all its split rows in **one transaction**; any failure rolls both back.
   The group row is locked (`SELECT ... FOR UPDATE`) so concurrent writers to one group are serialised.

## 13. Balance calculation methodology

Everything is derived from persisted `expense_splits` and `settlements`; nothing is cached.

1. **Ledger entries** `(debtor, creditor, paise)`: for each split of user U on an expense paid by P
   with `U != P` -> `(U, P, share)` (the payer's own share is never a debt); for each repayment
   "A paid B" -> `(A, B, -amount)`.
   The aggregation is a single `SUM ... GROUP BY` query per source.
2. **Net position** per user = total paid - total owed (after repayments). Positive: should receive;
   negative: owes. Net positions of a group always sum to zero.
3. **Pairwise view (`/balances`)**: net opposite directions between each pair (A owes B 400 and B owes A 300
   -> A owes B 100), then cancel circular debts (A->B->C->A) because they change nobody's net position.
   The result has no self-debts, no contradictory pairs, no zero entries, and a fully settled group is `{}`.
4. `group_id` limits all of this to one group; without it all groups are combined.

Example (Mohit 1200, Rahul 900, Ankit 600, three members): shares 400/300/200 ->
net Mohit **+300**, Rahul **0**, Ankit **-300**. Pairwise: Rahul owes Mohit 100, Ankit owes Mohit 200,
Ankit owes Rahul 100.

## 14. Smart settlement algorithm

`GET /groups/{id}/settlements/suggestions` runs a **greedy debt-simplification** on the net positions:

1. Put users with positive net in a max-heap (creditors) and users with negative net in another (debtors).
2. Pop the largest debtor and the largest creditor; `pay = min(debt, credit)`.
3. Record "debtor pays creditor `pay`"; reduce both; push back whoever still has a balance.
4. Repeat until both heaps are empty (ties are broken by user id, so output is deterministic).

Example from the brief: Mohit +500, Rahul +300, Ankit -400, Sameer -400 ->
Ankit pays Mohit 400, Sameer pays Rahul 300, Sameer pays Mohit 100 (3 payments).

* **Guarantees:** no self payments, no zero/negative payments, total paid = total received, after all
  payments every net position is zero. Each payment settles at least one person, so at most
  *n - 1* payments for *n* people with a non-zero balance.
* **Complexity:** O(n log n) time, O(n) space.
* **Honest limitation:** this is a practical **heuristic**. It does not always find the globally minimum
  number of payments (that is NP-hard, equivalent to partitioning balances into zero-sum subsets);
  it is just far better than paying every pairwise debt.
* **Assumption:** any member may pay any other member (e.g. UPI), so only net positions matter.

## 15. Product enhancement explanation

**Feature: Smart Settlement suggestions** (plus recorded repayments so the plan can be acted on).

* **Why:** the last step of every trip is "who sends money to whom?". The pairwise view can list many
  small cross-debts; real people want the shortest list.
* **Problem solved:** with the three-expense example the pairwise view needs 3 payments; the plan needs 1
  (Ankit pays Mohit 300). The response also includes `pairwise_transaction_count` for comparison.
* **Design decisions:** the algorithm works only on integer net positions (exact, deterministic); it is a
  pure function separate from the database; the endpoint is read-only (suggest, then explicitly record);
  repayments are validated against *net* positions so a member can pay exactly what the plan suggests,
  and executing the whole plan leaves every net balance - and `/balances` - at zero.
* **Trade-offs:** a heuristic instead of an exact optimum (documented above); the plan may ask someone to pay a person
  they never directly owed (fine for UPI, not for cash-only groups); suggestions are per group, not across groups.

## 16. Installation instructions

Requirements: Python 3.11+, and either Docker (recommended) or a local PostgreSQL server (the project was tested with PostgreSQL 16).

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows;  on Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## 17. Environment configuration

Copy [`.env.example`](.env.example) to `.env` and set your own values (`.env` is git-ignored; no
credentials are stored in the repository):

| Variable | Used by | Meaning |
|---|---|---|
| `DATABASE_URL` | app, Alembic | e.g. `postgresql+psycopg://user:pass@localhost:5432/dbname` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | docker-compose | credentials for the PostgreSQL container (required) |
| `POSTGRES_HOST_PORT`, `API_PORT` | docker-compose | optional host ports (defaults 5432 / 8000) |
| `TEST_DATABASE_URL` | pytest | optional: run tests on an *empty* PostgreSQL database instead of SQLite |

## 18. Database setup

Without Docker, create an empty database and user in your PostgreSQL server and put its URL in `DATABASE_URL`.
With Docker you can start only the database: `docker compose up -d db`.

## 19. Alembic migration instructions

```bash
alembic upgrade head      # create / update the schema
alembic downgrade base    # drop everything
alembic check             # confirm models and migrations agree
```

The API container runs `alembic upgrade head` automatically on startup. Tables are *only* created by
migrations, never by the application.

## 20. Running the application

```bash
alembic upgrade head
uvicorn app.main:app --reload
```
Open http://localhost:8000/docs.

## 21. Running with Docker

```bash
cp .env.example .env          # then edit the passwords
docker compose up --build
```
* `db`: PostgreSQL 16 with a health check; data persists in the `postgres_data` volume.
* `api`: waits for `db` to be healthy, applies migrations, serves on http://localhost:8000.
* Stop with `docker compose down` (add `-v` to also delete the database volume).

## 22. Running automated tests

```bash
pytest                                  # default: temporary SQLite file, no setup needed
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/expense_test pytest   # real PostgreSQL
```
The PostgreSQL database must be empty and disposable: the tests drop and recreate its tables.

**Last verified results** (run during development of this repository):

| Database | Result |
|---|---|
| SQLite | 446 passed |
| PostgreSQL 16 (Docker) | 446 passed |

Coverage by theme: user & group management, duplicate membership, expense creation and validation,
equal/unequal/participant splits, rounding (including 1 paisa over 3 people), atomic rollback,
historical splits unaffected by new members, balances (single/multiple expenses, equal payers,
one payer, multiple groups, rounding), circular-debt cancellation, the greedy algorithm (300 randomised
balance sets checking no self payments, no negative payments, totals equal, everyone settled, <= n-1
payments), repayment validation and race safety of the schema, database constraints, and a migration
test that compares the Alembic schema with the models.

## 23. Assumptions

* Currency is INR; amounts have at most 2 decimals (paise).
* "Split equally among all members" means *current* members at the time the expense is created.
* The payer is a member of the group and takes part in the default split.
* Names identify users in responses, so user names are unique, ignoring case.
* There is no authentication (not required); anyone can call any endpoint.
* In the `/balances` response, a person appears only while they owe someone.
* `GET /balances` without `group_id` combines all groups.
* In custom `participants` / `splits` modes the payer may be left out (they paid for others).
* Custom split amounts must be positive (a zero share is pointless); equal splits may yield a 0 share for tiny amounts.

## 24. Design decisions

* Integer paise and `Decimal` input - exact arithmetic, deterministic remainder distribution.
* `expense_splits` as a historical record, not derived from membership.
* Business rules in services, mirrored by database constraints (defence in depth).
* `GET /groups/{id}/settlements/suggestions` (a computed plan) is separate from `/settlements` (recorded
  facts), so "suggestion" and "history" never mix.
* Repayment validation uses net positions rather than a single pair so the smart plan is executable.
* One error envelope for every failure; raw database errors are logged, never returned.
* No repository layer, no authentication, no frontend - to avoid over-engineering for the scope.
* Money in JSON is a number in rupees (as in the assignment's examples) instead of strings.

## 25. Trade-offs

* JSON numbers are simple and match the brief, but a client that parses them as binary floats could
  misrepresent values; amounts are exact at two decimals, and all server-side maths is integer.
* Leftover paise always go to the lowest user ids: deterministic and simple, but not rotated for fairness.
* Pairwise balances cancel circular debts: they stay consistent with net positions, but a pair's displayed
  figure can differ from the raw sum of their direct expenses.
* Reading balances aggregates in SQL on every call: always correct, no cache invalidation, but not
  built for millions of rows.

## 26. Limitations

* Greedy settlement is a heuristic, not a proven minimum.
* No update/delete of expenses, members or users; no pagination on list endpoints.
* "Splits add up to the amount" is enforced in application code inside the transaction, not by a database constraint.
* The default split uses all members at creation time; there is no way to exclude someone except `participants`.
* Single currency, no authentication/authorisation, no rate limiting.
* The unit tests do not run a load test; concurrency safety was checked manually against PostgreSQL
  (12 parallel repayments of one debt: exactly one accepted).

## 27. Future improvements

Authentication and per-user access to groups, edit/delete (reversal) of expenses, percentage / share-based
splits, expense categories and monthly summaries, pagination, multi-currency, a database trigger asserting
that splits sum to the expense, CI pipeline, an exact (subset-sum) settlement mode for small groups.

## 28. Project ownership and contributors

* **Project Owner and Lead Developer: Muhammed Aabir Turabi** (repository owner).
* This implementation was produced with the help of an AI coding assistant (Claude Code) and is
  submitted by the owner.

## 29. Requirement checklist (summary)

| Assignment requirement | Where | Verified by |
|---|---|---|
| Create / list users | `routes/users.py`, `services/user_service.py` | `tests/test_users.py` |
| Create group, add / list members | `routes/groups.py`, `services/group_service.py` | `tests/test_groups.py` |
| Add expense: amount > 0, valid group, equal split, payer owes nothing | `services/expense_service.py`, `utils/money.py` | `tests/test_expenses.py`, `tests/test_money.py` |
| List group expenses | `routes/expenses.py` | `tests/test_expenses.py` |
| Balance calculation + structured API | `services/balance_service.py`, `routes/balances.py` | `tests/test_balances.py` |
| Own database schema, documented | `app/models/`, `alembic/`, `docs/database_schema.md` | `tests/test_migrations.py`, constraint tests |
| Mandatory product enhancement (+ why / problem / decisions / trade-offs) | `services/settlement_service.py`, sections 14-15 | `tests/test_settlements.py` |
| Bonus: balance settlement | `POST /settlements` | `tests/test_settlements.py` |
| Bonus: unequal split | `splits` field of `POST /expenses` | `tests/test_expenses.py` |
| Bonus: unit tests | `tests/` | 446 passed |
| Bonus: Docker | `Dockerfile`, `docker-compose.yml` | stack started and exercised end to end |
