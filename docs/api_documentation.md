# API documentation

Interactive documentation (Swagger UI) is served at **`/docs`**, ReDoc at `/redoc` and the OpenAPI
document at `/openapi.json`. All bodies are JSON.

**Money:** amounts are rupees as JSON numbers with at most 2 decimals, both in requests (`1200`,
`19.99`; `1.005` is rejected) and responses (`400`, `33.34`). Internally everything is integer paise.

**Errors** always look like `{"error": {"code": "...", "message": "...", "details": [...]}}`
(see [architecture.md](architecture.md#error-handling)).

| Method & path | Purpose | Success | Errors |
|---|---|---|---|
| `POST /users` | Create a user | 201 | 409 duplicate name, 422 |
| `GET /users` | List users | 200 | - |
| `POST /groups` | Create a group | 201 | 422 |
| `POST /groups/{group_id}/members` | Add a user to a group | 201 | 404 group/user, 409 duplicate, 422 |
| `GET /groups/{group_id}/members` | List members | 200 | 404 |
| `POST /expenses` | Record a shared expense | 201 | 404 group/payer, 422 |
| `GET /groups/{group_id}/expenses` | Expense history of a group | 200 | 404 |
| `GET /balances[?group_id=]` | Who owes whom | 200 | 404, 422 |
| `GET /groups/{group_id}/settlements/suggestions` | **Simplified settlement plan (greedy)** | 200 | 404 |
| `POST /settlements` | Record a real repayment | 201 | 404, 422 |
| `GET /groups/{group_id}/settlements` | Repayment history | 200 | 404 |
| `GET /health` | Liveness + database check | 200 | 500 |

The examples below were produced by running the service against PostgreSQL.

## Users

`POST /users`
```json
{"name": "Mohit"}
```
`201`
```json
{"id": 1, "name": "Mohit", "created_at": "2026-11-06T14:52:23.444367Z"}
```
Names are trimmed, 1-100 characters, unique ignoring case. `{"name": ""}` -> `422 VALIDATION_ERROR`;
a second `mohit` -> `409 CONFLICT`.

`GET /users` -> `200` list of users (`[]` when empty).

## Groups

`POST /groups` `{"name": "Goa Trip"}` -> `201 {"id": 1, "name": "Goa Trip", "created_at": "..."}`

`POST /groups/1/members`
```json
{"user_id": 2}
```
`201`
```json
{"group_id": 1, "user_id": 2, "name": "Rahul", "joined_at": "2026-11-06T14:52:23.546451Z"}
```
The assignment's variant `{"group_id": 1, "user_id": 2}` is also accepted; a `group_id` that differs
from the URL gives `422`. Adding the same user again -> `409`:
`{"error": {"code": "CONFLICT", "message": "User 2 is already a member of group 1"}}`

`GET /groups/1/members` -> `200` `[{"group_id": 1, "user_id": 1, "name": "Mohit", "joined_at": "..."}, ...]`
(`[]` for a group without members, `404` for an unknown group).

## Expenses

`POST /expenses` - **default: equal split among all current members of the group**
```json
{"group_id": 1, "paid_by": 1, "amount": 1200, "description": "Dinner"}
```
`201`
```json
{
  "id": 1, "group_id": 1, "description": "Dinner", "amount": 1200,
  "paid_by": "Mohit", "paid_by_id": 1, "created_at": "2026-11-06T14:52:23.598690Z",
  "splits": [
    {"user_id": 1, "name": "Mohit", "amount": 400},
    {"user_id": 2, "name": "Rahul", "amount": 400},
    {"user_id": 3, "name": "Ankit", "amount": 400}
  ]
}
```
Rules: `amount > 0` with at most 2 decimals; group and payer must exist (404); payer must be a member
(422); `description` required (1-255 chars). Leftover paise from an uneven split go to the lowest user ids:
100 split three ways -> `33.34 / 33.33 / 33.33`.

Optional fields (mutually exclusive):

* `"participants": [1, 2]` - equal split among only those members.
* `"splits": [{"user_id": 1, "amount": 500}, {"user_id": 2, "amount": 300}, {"user_id": 3, "amount": 200}]` -
  **unequal split**. Every user must be a group member, no duplicates, every amount > 0, and the
  amounts must add up exactly to `amount` (otherwise 422).

`GET /groups/1/expenses` -> `200`, the same objects as above in creation order. The assignment's fields
`description`, `amount`, `paid_by` (payer **name**) are present; `id`, `paid_by_id`, `created_at` and
`splits` are extra.

## Balances

`GET /balances?group_id=1` (one group - recommended) or `GET /balances` (all groups combined; debts from
different groups can cancel each other out)
```json
{"Rahul": {"owes": {"Mohit": 400}}, "Ankit": {"owes": {"Mohit": 400}}}
```
Only people who currently owe someone appear; settled pairs are omitted; `{}` means nothing is owed.
After three expenses (Mohit 1200, Rahul 900, Ankit 600) the same endpoint returns the netted pairwise
view:
```json
{"Rahul": {"owes": {"Mohit": 100}}, "Ankit": {"owes": {"Mohit": 200, "Rahul": 100}}}
```

## Smart settlement

`GET /groups/1/settlements/suggestions`
```json
{
  "group_id": 1,
  "net_balances": [
    {"user_id": 1, "name": "Mohit", "net_balance": 300},
    {"user_id": 2, "name": "Rahul", "net_balance": 0},
    {"user_id": 3, "name": "Ankit", "net_balance": -300}
  ],
  "payments": [
    {"from_user_id": 3, "from_user": "Ankit", "to_user_id": 1, "to_user": "Mohit", "amount": 300}
  ],
  "transaction_count": 1,
  "pairwise_transaction_count": 3
}
```
`net_balance` is positive when the person should receive money and negative when they owe.
`pairwise_transaction_count` is how many payments the plain pairwise view (`/balances`) would need.
The endpoint only suggests; it changes nothing.

## Repayments

`POST /settlements`
```json
{"group_id": 1, "paid_by": 3, "paid_to": 1, "amount": 300, "note": "UPI"}
```
`201`
```json
{"id": 1, "group_id": 1, "paid_by": "Ankit", "paid_by_id": 3, "paid_to": "Mohit", "paid_to_id": 1,
 "amount": 300, "note": "UPI", "created_at": "2026-11-06T14:52:23.758037Z"}
```
A repayment is accepted only if the payer currently owes money overall, the receiver is currently owed
money overall, and `amount` does not exceed either figure; otherwise `422`:
`{"error": {"code": "BUSINESS_RULE_VIOLATION", "message": "Settlement exceeds what can be settled between these users (payer owes 0, receiver is owed 0)"}}`.
Self payments, non-members and non-positive amounts are rejected too.
Repayments never edit expenses; they are added to the group's ledger and the balances update.

`GET /groups/1/settlements` -> `200` list of repayments in creation order.

## Validation error example

`POST /expenses` with `"amount": 0` -> `422`
```json
{"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed",
           "details": [{"field": "amount", "message": "Input should be greater than 0"}]}}
```
