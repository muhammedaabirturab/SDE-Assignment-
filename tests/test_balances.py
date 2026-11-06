from app.services.balance_service import net_positions, pairwise_debts


# ------------------------------------------------------- pure engine tests

def test_net_positions_sum_to_zero():
    # (debtor, creditor, paise)
    ledger = [(2, 1, 400), (3, 1, 400), (1, 2, 300), (3, 2, 300)]
    net = net_positions(ledger)
    assert net == {1: 500, 2: 200, 3: -700}
    assert sum(net.values()) == 0


def test_pairwise_nets_opposite_directions():
    # 2 owes 1: 400; 1 owes 2: 300  ->  only "2 owes 1: 100" remains
    assert pairwise_debts([(2, 1, 400), (1, 2, 300)]) == {(2, 1): 100}


def test_pairwise_drops_settled_pairs_and_self_debts():
    assert pairwise_debts([(2, 1, 400), (1, 2, 400), (3, 3, 50)]) == {}


def test_pairwise_cancels_circular_debts():
    # 1 owes 2, 2 owes 3, 3 owes 1 (100 each) changes nobody's net position.
    assert pairwise_debts([(1, 2, 100), (2, 3, 100), (3, 1, 100)]) == {}


def test_pairwise_partially_cancels_a_cycle_and_keeps_net_positions():
    ledger = [(1, 2, 300), (2, 3, 200), (3, 1, 100), (4, 1, 50)]
    debts = pairwise_debts(ledger)
    assert debts == {(1, 2): 200, (2, 3): 100, (4, 1): 50}
    rebuilt = net_positions([(d, c, a) for (d, c), a in debts.items()])
    assert rebuilt == net_positions(ledger)


def test_pairwise_result_is_acyclic_and_matches_net_positions_randomly():
    import random

    for seed in range(200):
        rng = random.Random(seed)
        ledger = [(rng.randint(1, 6), rng.randint(1, 6), rng.randint(1, 5000)) for _ in range(15)]
        debts = pairwise_debts(ledger)
        assert all(amount > 0 and d != c for (d, c), amount in debts.items())
        assert not any((c, d) in debts for (d, c) in debts)
        net = {u: v for u, v in net_positions(ledger).items() if v}
        rebuilt = {u: v for u, v in net_positions(
            [(d, c, a) for (d, c), a in debts.items()]).items() if v}
        assert rebuilt == net
        # acyclic debts + zero net position for everyone  =>  no debts left
        if not net:
            assert debts == {}


# ---------------------------------------------------------- API-level cases

def test_case_1_single_expense_matches_assignment_example(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    assert api.balances() == {
        "Rahul": {"owes": {"Mohit": 400}},
        "Ankit": {"owes": {"Mohit": 400}},
    }


def test_case_2_multiple_expenses_by_different_payers(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    api.expense(trip["group"], trip["rahul"], 900)
    api.expense(trip["group"], trip["ankit"], 600)

    plan = api.plan(trip["group"])
    nets = {n["name"]: n["net_balance"] for n in plan["net_balances"]}
    assert nets == {"Mohit": 300, "Rahul": 0, "Ankit": -300}
    assert plan["payments"] == [
        {"from_user_id": trip["ankit"], "from_user": "Ankit",
         "to_user_id": trip["mohit"], "to_user": "Mohit", "amount": 300}
    ]

    # Pairwise view: opposite debts are netted, nothing contradictory remains.
    assert api.balances() == {
        "Rahul": {"owes": {"Mohit": 100}},
        "Ankit": {"owes": {"Mohit": 200, "Rahul": 100}},
    }


def test_case_3_everyone_pays_equally_leaves_nothing_outstanding(trip, api):
    for payer in (trip["mohit"], trip["rahul"], trip["ankit"]):
        api.expense(trip["group"], payer, 900)
    assert api.balances() == {}
    plan = api.plan(trip["group"])
    assert plan["payments"] == []
    assert all(n["net_balance"] == 0 for n in plan["net_balances"])


def test_case_4_one_person_pays_for_everyone(api):
    users = [api.user(name) for name in ("Mohit", "Rahul", "Ankit", "Sameer")]
    group = api.group("Trip", tuple(users))
    api.expense(group, users[0], 2000)
    assert api.balances() == {
        "Rahul": {"owes": {"Mohit": 500}},
        "Ankit": {"owes": {"Mohit": 500}},
        "Sameer": {"owes": {"Mohit": 500}},
    }


def test_case_5_groups_do_not_affect_each_other(trip, api):
    office = api.group("Office", (trip["mohit"], trip["rahul"]))
    api.expense(trip["group"], trip["mohit"], 1200)
    api.expense(office, trip["rahul"], 100)

    assert api.balances(trip["group"]) == {
        "Rahul": {"owes": {"Mohit": 400}}, "Ankit": {"owes": {"Mohit": 400}}}
    assert api.balances(office) == {"Mohit": {"owes": {"Rahul": 50}}}
    # Without group_id the groups are combined: 400 - 50 = 350.
    assert api.balances() == {
        "Rahul": {"owes": {"Mohit": 350}}, "Ankit": {"owes": {"Mohit": 400}}}
    # Each group's smart plan only involves that group's own money.
    assert api.plan(office)["payments"][0]["amount"] == 50


def test_case_6_rounding_never_loses_a_paisa(trip, api):
    api.expense(trip["group"], trip["mohit"], 100)      # 33.34 / 33.33 / 33.33
    api.expense(trip["group"], trip["rahul"], 100.01)   # 33.34 / 33.34 / 33.33
    plan = api.plan(trip["group"])
    nets = [n["net_balance"] for n in plan["net_balances"]]
    assert round(sum(nets), 2) == 0
    paid_out = round(sum(p["amount"] for p in plan["payments"] if p["amount"] > 0), 2)
    received = round(sum(n for n in nets if n > 0), 2)
    assert paid_out == received


def test_circular_debts_cancel_out(api):
    a, b, c = api.user("Mohit"), api.user("Rahul"), api.user("Ankit")
    group = api.group("Loop", (a, b, c))
    api.expense(group, a, 100, splits=[{"user_id": b, "amount": 100}])
    api.expense(group, b, 100, splits=[{"user_id": c, "amount": 100}])
    api.expense(group, c, 100, splits=[{"user_id": a, "amount": 100}])
    assert api.balances(group) == {}
    assert api.plan(group)["payments"] == []


def test_balances_for_unknown_group(client):
    assert client.get("/balances", params={"group_id": 999}).status_code == 404


def test_balances_rejects_invalid_group_id(client):
    assert client.get("/balances", params={"group_id": "abc"}).status_code == 422


def test_balances_on_empty_database(client):
    response = client.get("/balances")
    assert response.status_code == 200
    assert response.json() == {}


def test_balances_follow_new_expenses_dynamically(trip, api):
    api.expense(trip["group"], trip["mohit"], 1200)
    api.expense(trip["group"], trip["mohit"], 600)
    assert api.balances()["Rahul"]["owes"]["Mohit"] == 600
