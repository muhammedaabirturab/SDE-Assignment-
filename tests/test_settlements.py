import random

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Expense, ExpenseSplit, Settlement
from app.services.settlement_service import compute_settlement_plan


def apply(net: dict[int, int], payments) -> dict[int, int]:
    """Net positions after the given (from, to, amount) payments are made."""
    result = dict(net)
    for debtor, creditor, amount in payments:
        result[debtor] += amount
        result[creditor] -= amount
    return result


# ------------------------------------------------- the greedy algorithm itself

def test_assignment_example_uses_fewer_payments_than_pairing_everyone():
    # Mohit +500, Rahul +300, Ankit -400, Sameer -400
    net = {1: 50000, 2: 30000, 3: -40000, 4: -40000}
    payments = compute_settlement_plan(net)
    assert apply(net, payments) == {1: 0, 2: 0, 3: 0, 4: 0}
    assert len(payments) == 3          # naive pairing of every debtor with every creditor: 4
    assert payments == [(3, 1, 40000), (4, 2, 30000), (4, 1, 10000)]


def test_identifies_creditors_and_debtors():
    payments = compute_settlement_plan({1: 700, 2: -300, 3: -400, 4: 0})
    payers = {p[0] for p in payments}
    receivers = {p[1] for p in payments}
    assert payers == {2, 3}
    assert receivers == {1}            # user 4 is settled and takes no part


def test_nothing_to_settle():
    assert compute_settlement_plan({}) == []
    assert compute_settlement_plan({1: 0, 2: 0}) == []


def test_rejects_unbalanced_input():
    with pytest.raises(ValueError):
        compute_settlement_plan({1: 100, 2: -50})


def test_plan_is_deterministic():
    net = {1: 100, 2: 100, 3: -100, 4: -100}
    assert compute_settlement_plan(net) == compute_settlement_plan(dict(reversed(net.items())))


@pytest.mark.parametrize("seed", range(300))
def test_plan_invariants_on_random_balances(seed):
    rng = random.Random(seed)
    people = rng.randint(1, 12)
    net = {user: rng.randint(-100_000, 100_000) for user in range(1, people + 1)}
    net[people] -= sum(net.values())            # make the total exactly zero
    payments = compute_settlement_plan(net)

    assert all(debtor != creditor for debtor, creditor, _ in payments)   # no self payments
    assert all(amount > 0 for _, _, amount in payments)                  # no negative / zero
    assert sum(a for _, _, a in payments) == sum(v for v in net.values() if v > 0)
    assert all(v == 0 for v in apply(net, payments).values())            # everyone settled
    outstanding = sum(1 for v in net.values() if v != 0)
    assert len(payments) <= max(outstanding - 1, 0)                      # at most n - 1


def test_total_paid_by_debtors_equals_total_received_by_creditors():
    net = {1: 500, 2: 300, 3: -400, 4: -400}
    payments = compute_settlement_plan(net)
    paid, received = {}, {}
    for debtor, creditor, amount in payments:
        paid[debtor] = paid.get(debtor, 0) + amount
        received[creditor] = received.get(creditor, 0) + amount
    assert sum(paid.values()) == sum(received.values())
    assert paid == {3: 400, 4: 400}
    assert received == {1: 500, 2: 300}


# ---------------------------------------------------- suggestions via the API

def test_suggestion_endpoint_for_assignment_scenario(api):
    mohit, rahul, ankit, sameer = (api.user(n) for n in ("Mohit", "Rahul", "Ankit", "Sameer"))
    group = api.group("Trip", (mohit, rahul, ankit, sameer))
    # Net: Mohit +500, Rahul +300, Ankit -400, Sameer -400 via custom splits
    api.expense(group, mohit, 800, splits=[{"user_id": ankit, "amount": 400},
                                           {"user_id": sameer, "amount": 400}])
    api.expense(group, rahul, 800, splits=[{"user_id": ankit, "amount": 400},
                                           {"user_id": sameer, "amount": 400}])
    api.expense(group, ankit, 400, splits=[{"user_id": mohit, "amount": 200},
                                           {"user_id": rahul, "amount": 200}])
    plan = api.plan(group)
    nets = {n["name"]: n["net_balance"] for n in plan["net_balances"]}
    assert nets == {"Mohit": 600, "Rahul": 600, "Ankit": -400, "Sameer": -800}
    assert plan["transaction_count"] == len(plan["payments"]) <= 3
    assert plan["transaction_count"] <= plan["pairwise_transaction_count"]
    assert sum(p["amount"] for p in plan["payments"]) == 1200


def test_suggestions_for_empty_and_unknown_group(api, client):
    group = api.group()
    plan = api.plan(group)
    assert plan["payments"] == [] and plan["net_balances"] == []
    assert client.get("/groups/999/settlements/suggestions").status_code == 404


def test_suggestion_is_read_only(trip, api, db):
    api.expense(trip["group"], trip["mohit"], 1200)
    api.plan(trip["group"])
    assert db.scalar(select(func.count(Settlement.id))) == 0


def test_executing_the_suggested_plan_settles_the_group(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    api.expense(trip["group"], trip["rahul"], 900)
    api.expense(trip["group"], trip["ankit"], 600)
    for payment in api.plan(trip["group"])["payments"]:
        response = api.settle(trip["group"], payment["from_user_id"], payment["to_user_id"],
                              payment["amount"])
        assert response.status_code == 201, response.text
    after = api.plan(trip["group"])
    assert after["payments"] == []
    assert all(n["net_balance"] == 0 for n in after["net_balances"])
    assert after["pairwise_transaction_count"] == 0
    assert api.balances(trip["group"]) == {}


# ------------------------------------------------ recording real repayments

def test_repayment_clears_the_debt(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    response = api.settle(trip["group"], trip["rahul"], trip["mohit"], 400, note="UPI")
    assert response.status_code == 201
    body = response.json()
    assert (body["paid_by"], body["paid_to"], body["amount"], body["note"]) == (
        "Rahul", "Mohit", 400, "UPI")
    assert "created_at" in body
    assert api.balances() == {"Ankit": {"owes": {"Mohit": 400}}}


def test_partial_repayment(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    api.settle(trip["group"], trip["rahul"], trip["mohit"], 150.50)
    assert api.balances()["Rahul"] == {"owes": {"Mohit": 249.5}}


def test_repayment_does_not_touch_expense_history(trip, api, db):
    api.expense(trip["group"], trip["mohit"], 1200)
    api.settle(trip["group"], trip["rahul"], trip["mohit"], 400)
    assert db.scalar(select(func.count(Expense.id))) == 1
    assert db.scalar(select(func.sum(ExpenseSplit.share_paise))) == 120000
    history = api.client.get(f"/groups/{trip['group']}/settlements").json()
    assert [(s["paid_by"], s["paid_to"], s["amount"]) for s in history] == [("Rahul", "Mohit", 400)]


def test_cannot_settle_more_than_is_owed(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    assert api.settle(trip["group"], trip["rahul"], trip["mohit"], 400.01).status_code == 422
    assert api.settle(trip["group"], trip["rahul"], trip["mohit"], 400).status_code == 201
    # Already fully settled: any further payment is excessive.
    assert api.settle(trip["group"], trip["rahul"], trip["mohit"], 1).status_code == 422


def test_cannot_pay_someone_who_owes_you(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    response = api.settle(trip["group"], trip["mohit"], trip["rahul"], 100)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


def test_settlement_validation(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    outsider = api.user("Sameer")
    assert api.settle(trip["group"], trip["rahul"], trip["rahul"], 10).status_code == 422
    assert api.settle(trip["group"], trip["rahul"], trip["mohit"], 0).status_code == 422
    assert api.settle(trip["group"], trip["rahul"], trip["mohit"], -5).status_code == 422
    assert api.settle(trip["group"], trip["rahul"], trip["mohit"], 1.005).status_code == 422
    assert api.settle(trip["group"], outsider, trip["mohit"], 10).status_code == 422
    assert api.settle(trip["group"], trip["rahul"], 999, 10).status_code == 404
    assert api.settle(999, trip["rahul"], trip["mohit"], 10).status_code == 404
    assert api.client.get(f"/groups/{trip['group']}/settlements").json() == []


def test_settlements_are_scoped_to_their_group(trip, api):
    office = api.group("Office", (trip["mohit"], trip["rahul"]))
    api.expense(trip["group"], trip["mohit"], 1200)
    # Rahul owes Mohit in Goa Trip only; in Office nobody owes anything.
    assert api.settle(office, trip["rahul"], trip["mohit"], 100).status_code == 422
    assert api.settle(trip["group"], trip["rahul"], trip["mohit"], 100).status_code == 201
    assert api.client.get(f"/groups/{office}/settlements").json() == []


def test_settlement_history_of_unknown_group(client):
    assert client.get("/groups/999/settlements").status_code == 404


def test_database_rejects_self_payment_and_non_positive_amounts(trip, db):
    for paid_to, amount in ((trip["mohit"], 100), (trip["rahul"], 0)):
        db.add(Settlement(group_id=trip["group"], paid_by=trip["mohit"], paid_to=paid_to,
                          amount_paise=amount))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
