"""
Balance calculation and settlement optimization service for SplitTrip.

The settlement algorithm minimizes the number of transactions needed
to zero out all debts in a group (greedy min-cash-flow approach).
"""
from decimal import Decimal
from collections import defaultdict


def calculate_balances(trip):
    """
    Calculate net balance for each member of a trip.
    Positive = the member is owed money.
    Negative = the member owes money.
    Returns: dict {user_id: {'user': User, 'balance': Decimal}}
    """
    members = trip.get_members()
    balances = {m.id: {'user': m, 'balance': Decimal('0')} for m in members}

    for expense in trip.expenses.select_related('paid_by').prefetch_related('expense_splits__user'):
        payer_id = expense.paid_by.id
        if payer_id in balances:
            balances[payer_id]['balance'] += expense.amount

        for split in expense.expense_splits.all():
            uid = split.user.id
            if uid in balances:
                balances[uid]['balance'] -= split.amount_owed

    # Apply settlements
    for settlement in trip.settlements.select_related('payer', 'receiver'):
        if settlement.payer.id in balances:
            balances[settlement.payer.id]['balance'] -= settlement.amount
        if settlement.receiver.id in balances:
            balances[settlement.receiver.id]['balance'] += settlement.amount

    return balances


def calculate_who_owes_whom(trip):
    """
    Build a matrix of direct debts between pairs of users.
    Returns: list of {'from': user, 'to': user, 'amount': Decimal}
    """
    debts = defaultdict(lambda: defaultdict(Decimal))

    for expense in trip.expenses.select_related('paid_by').prefetch_related('expense_splits__user'):
        payer = expense.paid_by
        for split in expense.expense_splits.all():
            if split.user != payer:
                debts[split.user.id][payer.id] += split.amount_owed

    # Apply settlements (reduce debts)
    for settlement in trip.settlements.select_related('payer', 'receiver'):
        debts[settlement.payer.id][settlement.receiver.id] -= settlement.amount

    # Build user lookup
    user_map = {m.id: m for m in trip.get_members()}

    result = []
    for from_id, tos in debts.items():
        for to_id, amount in tos.items():
            if amount > Decimal('0.01') and from_id in user_map and to_id in user_map:
                result.append({
                    'from': user_map[from_id],
                    'to': user_map[to_id],
                    'amount': round(amount, 2),
                })
    return result


def calculate_optimized_settlements(trip):
    """
    Compute the minimum number of transactions to settle all debts.
    Uses a greedy algorithm on net balances (min-cash-flow).

    Returns: list of {'payer': user, 'receiver': user, 'amount': Decimal}
    """
    balances = calculate_balances(trip)

    creditors = []  # (balance, user) — positive
    debtors = []    # (balance, user) — negative

    for uid, data in balances.items():
        b = data['balance']
        if b > Decimal('0.01'):
            creditors.append([b, data['user']])
        elif b < Decimal('-0.01'):
            debtors.append([abs(b), data['user']])

    creditors.sort(key=lambda x: -x[0])
    debtors.sort(key=lambda x: -x[0])

    transactions = []

    i, j = 0, 0
    while i < len(creditors) and j < len(debtors):
        credit_amount, creditor = creditors[i]
        debt_amount, debtor = debtors[j]

        transfer = min(credit_amount, debt_amount)
        transfer = round(transfer, 2)

        transactions.append({
            'payer': debtor,
            'receiver': creditor,
            'amount': transfer,
        })

        creditors[i][0] -= transfer
        debtors[j][0] -= transfer

        if creditors[i][0] < Decimal('0.01'):
            i += 1
        if debtors[j][0] < Decimal('0.01'):
            j += 1

    return transactions


def create_equal_splits(expense, participants):
    """
    Create ExpenseSplit objects for an equal split expense.
    participants: queryset or list of User objects
    """
    from trips.models import ExpenseSplit
    count = len(participants)
    if count == 0:
        return

    per_person = round(expense.amount / count, 2)
    remainder = expense.amount - (per_person * count)

    splits = []
    for idx, user in enumerate(participants):
        amount = per_person + (remainder if idx == 0 else Decimal('0'))
        splits.append(ExpenseSplit(expense=expense, user=user, amount_owed=amount))

    ExpenseSplit.objects.bulk_create(splits)


def create_percentage_splits(expense, percentage_data):
    """
    percentage_data: list of {'user': User, 'percentage': Decimal}
    """
    from trips.models import ExpenseSplit
    splits = []
    for item in percentage_data:
        amount = round(expense.amount * item['percentage'] / 100, 2)
        splits.append(ExpenseSplit(
            expense=expense,
            user=item['user'],
            amount_owed=amount,
            percentage=item['percentage']
        ))
    ExpenseSplit.objects.bulk_create(splits)


def create_exact_splits(expense, exact_data):
    """
    exact_data: list of {'user': User, 'amount': Decimal}
    """
    from trips.models import ExpenseSplit
    splits = [
        ExpenseSplit(expense=expense, user=item['user'], amount_owed=item['amount'])
        for item in exact_data
    ]
    ExpenseSplit.objects.bulk_create(splits)
