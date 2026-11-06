import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Expense, ExpenseSplit
from app.services import expense_service


def shares_of(body: dict) -> dict[str, float]:
    return {s["name"]: s["amount"] for s in body["splits"]}


# ----------------------------------------------------------------- creation

def test_create_expense_successfully(trip, api):
    response = api.expense(trip["group"], trip["mohit"], 1200, "Dinner")
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["description"] == "Dinner"
    assert body["amount"] == 1200
    assert body["paid_by"] == "Mohit"
    assert body["paid_by_id"] == trip["mohit"]
    assert "created_at" in body


def test_expense_is_split_equally_and_payer_gets_own_share(trip, api):
    body = api.expense(trip["group"], trip["mohit"], 1200).json()
    assert shares_of(body) == {"Mohit": 400, "Rahul": 400, "Ankit": 400}


def test_shares_add_up_to_the_original_amount(trip, api, db):
    api.expense(trip["group"], trip["mohit"], 1200)
    total = db.scalar(select(func.sum(ExpenseSplit.share_paise)))
    assert total == db.scalar(select(Expense.amount_paise)) == 120000


def test_payer_does_not_owe_themselves(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    balances = api.balances()
    assert "Mohit" not in balances
    assert balances == {"Rahul": {"owes": {"Mohit": 400}}, "Ankit": {"owes": {"Mohit": 400}}}


def test_sole_member_paying_creates_no_debt(api):
    only = api.user("Mohit")
    group = api.group(members=(only,))
    assert api.expense(group, only, 500).status_code == 201
    assert api.balances() == {}


# --------------------------------------------------------------- validation

@pytest.mark.parametrize("amount", [0, -1, -0.01, "0"])
def test_reject_zero_or_negative_amount(trip, api, amount):
    response = api.expense(trip["group"], trip["mohit"], amount)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("amount", ["abc", None, 1.005, 12.345, 10**13])
def test_reject_malformed_amount(trip, api, amount):
    assert api.expense(trip["group"], trip["mohit"], amount).status_code == 422


def test_reject_missing_description(trip, api):
    response = api.client.post(
        "/expenses", json={"group_id": trip["group"], "paid_by": trip["mohit"], "amount": 10}
    )
    assert response.status_code == 422


def test_reject_unknown_group(trip, api):
    assert api.expense(999, trip["mohit"], 100).status_code == 404


def test_reject_unknown_payer(trip, api):
    assert api.expense(trip["group"], 999, 100).status_code == 404


def test_reject_payer_who_is_not_a_group_member(trip, api):
    outsider = api.user("Sameer")
    response = api.expense(trip["group"], outsider, 100)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


def test_reject_expense_without_valid_participants(trip, api):
    assert api.expense(trip["group"], trip["mohit"], 100, participants=[]).status_code == 422
    outsider = api.user("Sameer")
    response = api.expense(
        trip["group"], trip["mohit"], 100, participants=[trip["rahul"], outsider]
    )
    assert response.status_code == 422
    assert api.client.get(f"/groups/{trip['group']}/expenses").json() == []


def test_reject_duplicate_participants(trip, api):
    response = api.expense(
        trip["group"], trip["mohit"], 100, participants=[trip["rahul"], trip["rahul"]]
    )
    assert response.status_code == 422


def test_equal_split_among_chosen_participants(trip, api):
    body = api.expense(
        trip["group"], trip["mohit"], 900, participants=[trip["mohit"], trip["rahul"]]
    ).json()
    assert shares_of(body) == {"Mohit": 450, "Rahul": 450}
    assert api.balances() == {"Rahul": {"owes": {"Mohit": 450}}}


# ------------------------------------------------------- history & rounding

def test_historical_splits_do_not_change_when_members_join_later(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    before = api.client.get(f"/groups/{trip['group']}/expenses").json()

    sameer = api.user("Sameer")
    api.client.post(f"/groups/{trip['group']}/members", json={"user_id": sameer})

    after = api.client.get(f"/groups/{trip['group']}/expenses").json()
    assert after == before
    assert len(after[0]["splits"]) == 3
    assert "Sameer" not in api.balances()

    # ...but he shares the *next* expense.
    new = api.expense(trip["group"], trip["mohit"], 1200).json()
    assert shares_of(new) == {"Mohit": 300, "Rahul": 300, "Ankit": 300, "Sameer": 300}


def test_rounding_leftover_paise_are_distributed_not_lost(trip, api):
    body = api.expense(trip["group"], trip["mohit"], 100).json()
    # 100.00 / 3 = 33.333...: Mohit (lowest id) takes the extra paisa.
    assert shares_of(body) == {"Mohit": 33.34, "Rahul": 33.33, "Ankit": 33.33}
    assert api.balances() == {"Rahul": {"owes": {"Mohit": 33.33}},
                              "Ankit": {"owes": {"Mohit": 33.33}}}


def test_rounding_of_one_paisa(trip, api, db):
    api.expense(trip["group"], trip["mohit"], 0.01)
    rows = sorted(db.scalars(select(ExpenseSplit.share_paise)))
    assert rows == [0, 0, 1]


@pytest.mark.parametrize("amount", ["10.01", "99.99", "1000.07", "0.02", "7"])
def test_every_amount_splits_to_the_exact_total(trip, api, db, amount):
    api.expense(trip["group"], trip["mohit"], amount)
    paid = db.scalar(select(Expense.amount_paise))
    assert db.scalar(select(func.sum(ExpenseSplit.share_paise))) == paid


# ------------------------------------------------------------ unequal split

def test_unequal_split(trip, api):
    body = api.expense(
        trip["group"], trip["mohit"], 1000,
        splits=[{"user_id": trip["mohit"], "amount": 500},
                {"user_id": trip["rahul"], "amount": 300},
                {"user_id": trip["ankit"], "amount": 200}],
    ).json()
    assert shares_of(body) == {"Mohit": 500, "Rahul": 300, "Ankit": 200}
    assert api.balances() == {"Rahul": {"owes": {"Mohit": 300}}, "Ankit": {"owes": {"Mohit": 200}}}


def test_unequal_split_must_add_up(trip, api):
    response = api.expense(
        trip["group"], trip["mohit"], 1000,
        splits=[{"user_id": trip["mohit"], "amount": 500},
                {"user_id": trip["rahul"], "amount": 400}],
    )
    assert response.status_code == 422
    assert api.client.get(f"/groups/{trip['group']}/expenses").json() == []


def test_unequal_split_rejects_duplicates_nonmembers_and_bad_amounts(trip, api):
    outsider = api.user("Sameer")
    dup = [{"user_id": trip["rahul"], "amount": 500}, {"user_id": trip["rahul"], "amount": 500}]
    assert api.expense(trip["group"], trip["mohit"], 1000, splits=dup).status_code == 422
    out = [{"user_id": trip["rahul"], "amount": 500}, {"user_id": outsider, "amount": 500}]
    assert api.expense(trip["group"], trip["mohit"], 1000, splits=out).status_code == 422
    neg = [{"user_id": trip["rahul"], "amount": 1500}, {"user_id": trip["ankit"], "amount": -500}]
    assert api.expense(trip["group"], trip["mohit"], 1000, splits=neg).status_code == 422
    assert api.expense(trip["group"], trip["mohit"], 1000, splits=[]).status_code == 422


def test_cannot_combine_splits_and_participants(trip, api):
    response = api.expense(
        trip["group"], trip["mohit"], 100,
        participants=[trip["rahul"]],
        splits=[{"user_id": trip["rahul"], "amount": 100}],
    )
    assert response.status_code == 422


def test_payer_may_be_left_out_of_a_custom_split(trip, api):
    api.expense(trip["group"], trip["mohit"], 600,
                splits=[{"user_id": trip["rahul"], "amount": 300},
                        {"user_id": trip["ankit"], "amount": 300}])
    assert api.balances() == {"Rahul": {"owes": {"Mohit": 300}}, "Ankit": {"owes": {"Mohit": 300}}}


# ------------------------------------------------------------------ listing

def test_list_group_expenses(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200, "Dinner")
    api.expense(trip["group"], trip["rahul"], 300, "Taxi")
    response = api.client.get(f"/groups/{trip['group']}/expenses")
    assert response.status_code == 200
    body = response.json()
    assert [(e["description"], e["amount"], e["paid_by"]) for e in body] == [
        ("Dinner", 1200, "Mohit"), ("Taxi", 300, "Rahul")]


def test_list_only_returns_the_requested_groups_expenses(trip, api):
    other = api.group("Office", (trip["mohit"], trip["rahul"]))
    api.expense(trip["group"], trip["mohit"], 1200, "Dinner")
    api.expense(other, trip["rahul"], 50, "Coffee")
    goa = api.client.get(f"/groups/{trip['group']}/expenses").json()
    office = api.client.get(f"/groups/{other}/expenses").json()
    assert [e["description"] for e in goa] == ["Dinner"]
    assert [e["description"] for e in office] == ["Coffee"]


def test_list_expenses_of_group_without_expenses(trip, api):
    response = api.client.get(f"/groups/{trip['group']}/expenses")
    assert response.status_code == 200
    assert response.json() == []


def test_list_expenses_of_unknown_group(client):
    assert client.get("/groups/999/expenses").status_code == 404


# ------------------------------------------- atomicity & database-level rules

def test_expense_and_splits_are_saved_atomically(trip, api, db, monkeypatch):
    """If the splits cannot be saved, the expense row must not survive either."""
    outsider = api.user("Sameer")  # not a member -> DB composite FK must refuse it
    monkeypatch.setattr(
        expense_service, "calculate_shares",
        lambda payload, amount, members: {trip["mohit"]: 5000, outsider: 5000},
    )
    response = api.expense(trip["group"], trip["mohit"], 100)
    assert response.status_code == 409
    assert "Traceback" not in response.text and "psycopg" not in response.text
    assert db.scalar(select(func.count(Expense.id))) == 0
    assert db.scalar(select(func.count(ExpenseSplit.id))) == 0


def test_database_rejects_non_positive_expense_amount(trip, db):
    db.add(Expense(group_id=trip["group"], paid_by=trip["mohit"], amount_paise=0, description="x"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_database_rejects_payer_outside_the_group(trip, api, db):
    outsider = api.user("Sameer")
    db.add(Expense(group_id=trip["group"], paid_by=outsider, amount_paise=100, description="x"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_database_rejects_split_for_wrong_group(trip, api, db):
    other = api.group("Other", (trip["mohit"],))
    expense_id = api.expense(trip["group"], trip["mohit"], 300).json()["id"]
    db.add(
        ExpenseSplit(expense_id=expense_id, group_id=other, user_id=trip["mohit"], share_paise=0)
    )
    with pytest.raises(IntegrityError):
        db.commit()
