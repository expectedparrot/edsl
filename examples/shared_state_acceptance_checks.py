"""Independent live-answer/state checks for the fixed acceptance demo rosters.

These use actual decisions, not the predetermined answers from scripted mode.
They intentionally check the examples' default capacities, balances, and reserves.
"""

from collections import Counter


def check_options(row, question, expected):
    # Scripted fixtures replace model questions with compute expressions.
    if row.data["question_to_attributes"][question]["question_type"] != "compute":
        assert row.get_question_options(question) == expected


def check_application(name, results, state):
    expected_rows = {
        "survey_quota": 27,
        "posted_price_market": 4,
        "second_price_auction": 3,
        "uniform_price_auction": 3,
        "appointment_booking": 5,
        "balanced_assignment": 12,
    }
    assert len(results) == expected_rows[name], "Missing or extra participants"
    if name == "survey_quota":
        return check_quota(results, state["quota"])
    if name == "posted_price_market":
        return check_market(results, state["market"])
    if name.endswith("price_auction"):
        return check_auction(name, results, state["auction"]["auction"])
    if name == "appointment_booking":
        return check_booking(results, state["booking"])
    return check_assignment(results, state["balance"])


def check_quota(results, state):
    admissions = {}
    counts = Counter()
    for row in sorted(results, key=lambda r: int(r.agent.traits["respondent_id"][1:])):
        answer = row.answer
        group = answer.get("respondent_type")
        if counts["A"] == counts["B"] == 10:
            assert answer["enrollment_gate"] == "closed"
            assert group is None and answer.get("experience") is None
            continue
        assert answer["enrollment_gate"] == "open"
        assert group in ("A", "B", "Other")
        admitted = group in ("A", "B") and counts[group] < 10
        assert answer["quota_gate"] == ("admitted" if admitted else "screened_out")
        if admitted:
            admissions[row.agent.traits["respondent_id"]] = group
            counts[group] += 1
            assert (
                isinstance(answer["experience"], str) and answer["experience"].strip()
            )
        else:
            assert answer.get("experience") is None
    assert state["admissions"] == admissions
    return {"admitted": dict(counts), "screened_out": len(results) - len(admissions)}


def check_market(results, state):
    stock, seller_cash = 5, 0
    cash = dict.fromkeys("ABCD", 200)
    inventory = dict.fromkeys("ABCD", 0)
    orders = {}
    for row in sorted(results, key=lambda r: r.agent.traits["turn"]):
        answer, traits = row.answer, row.agent.traits
        quantity = answer.get("quantity")
        if stock == 0:
            assert answer["market_entry"] == "closed" and quantity is None
            continue
        assert answer["market_entry"] == "open"
        buyer = traits["buyer_id"]
        price = 20 + (5 - stock) * 5
        options = list(range(min(stock, cash[buyer] // price) + 1))
        check_options(row, "quantity", options)
        assert quantity in options
        status = "filled" if quantity else "passed"
        assert answer["order_receipt"] == status
        orders[traits["order_id"]] = (buyer, price, quantity, status)
        stock -= quantity
        inventory[buyer] += quantity
        cash[buyer] -= quantity * price
        seller_cash += quantity * price
    assert state["stock"] == stock and state["inventory"] == inventory
    assert state["cash"] == cash and state["seller_cash"] == seller_cash
    assert sum(cash.values()) + seller_cash == 800
    assert set(state["orders"]) == set(orders)
    for token, expected in orders.items():
        order = state["orders"][token]
        assert (
            tuple(order[k] for k in ("buyer_id", "price", "quantity", "status"))
            == expected
        )
    return {"stock": stock, "seller_cash": seller_cash, "inventory": inventory}


def check_auction(name, results, book):
    units, demand = (1, 1) if name == "second_price_auction" else (3, 2)
    bids = {
        row.agent.traits["bidder_id"]: [row.answer[f"bid_{i}"] for i in range(demand)]
        for row in results
    }
    assert book["bids"] == bids and book["settled"]
    for values in bids.values():
        assert all(type(bid) is int and 0 <= bid <= 200 for bid in values)
        assert values == sorted(values, reverse=True) and sum(values) <= 200
    eligible = sorted(
        (b for values in bids.values() for b in values if b >= 40), reverse=True
    )
    sold = min(units, len(eligible))
    price = (eligible[units] if len(eligible) > units else 40) if sold else None
    assert book["price"] == price
    assert set(book["allocations"]) == set(bids)
    assert sum(book["allocations"].values()) == sold
    assert book["remaining"] == units - sold
    winners, losers = [], []
    for bidder, values in bids.items():
        quantity = book["allocations"][bidder]
        assert 0 <= quantity <= demand
        winners.extend(values[:quantity])
        losers.extend(values[quantity:])
        assert book["payments"][bidder] == quantity * (price or 0)
        assert book["cash"][bidder] == 200 - book["payments"][bidder]
    assert not winners or min(winners) >= max([40, *losers])
    assert book["seller_cash"] == sold * (price or 0)
    assert sum(book["cash"].values()) + book["seller_cash"] == 600
    return {"bids": bids, "price": price, "allocations": book["allocations"]}


def check_booking(results, state):
    slots = ["09:00", "10:00", "11:00"]
    bookings = {}
    counts = Counter()
    for row in sorted(results, key=lambda r: r.agent.traits["turn"]):
        answer, traits = row.answer, row.agent.traits
        occupied = {b["slot"] for b in bookings.values() if b["status"] == "confirmed"}
        free = [s for s in slots if s not in occupied]
        if not free:
            assert answer["availability"] == "closed"
            assert all(
                answer.get(q) is None
                for q in ("slot", "confirmation", "booking_outcome")
            )
            counts["unavailable"] += 1
            continue
        assert answer["availability"] == "open" and answer["hold_status"] == "held"
        check_options(row, "slot", free)
        assert answer["slot"] in free
        assert answer["confirmation"] in ("Confirm", "Release")
        status = "confirmed" if answer["confirmation"] == "Confirm" else "released"
        assert answer["booking_outcome"] == status
        bookings[traits["reservation_id"]] = {
            "respondent_id": traits["respondent_id"],
            "slot": answer["slot"],
            "status": status,
        }
        counts[status] += 1
    assert state["bookings"] == bookings
    return dict(counts)


def check_assignment(results, state):
    assignments = {}
    for row in sorted(results, key=lambda r: r.agent.traits["turn"]):
        answer = row.answer
        age, experience, arm = (
            answer[k] for k in ("age_group", "experience", "assigned_arm")
        )
        assert age in ("Younger", "Older") and experience in ("New", "Experienced")
        assert arm in ("Control", "Treatment")
        scores = {
            candidate: sum(
                1 + (a["age"] == age) + (a["experience"] == experience)
                for a in assignments.values()
                if a["arm"] == candidate
            )
            for candidate in ("Control", "Treatment")
        }
        assert scores[arm] == min(
            scores.values()
        ), "Assignment did not minimize imbalance"
        assert isinstance(answer["response"], str) and answer["response"].strip()
        assignments[row.agent.traits["respondent_id"]] = {
            "age": age,
            "experience": experience,
            "arm": arm,
        }
    assert state["assignments"] == assignments
    return {
        "counts": dict(Counter(a["arm"] for a in assignments.values())),
        "assigned": len(assignments),
    }
