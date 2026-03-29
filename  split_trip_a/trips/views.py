import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction

from .models import Trip, Membership, Expense, ExpenseSplit, Settlement
from .forms import RegisterForm, TripForm, ExpenseForm, InviteForm, SettlementForm
from .services import (
    calculate_balances, calculate_optimized_settlements, calculate_who_owes_whom,
    create_equal_splits, create_percentage_splits, create_exact_splits,
)


# ─── Auth ───────────────────────────────────────────────────────────────────

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Compte créé avec succès ! Bienvenue sur SplitTrip 🎉")
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})


# ─── Dashboard ──────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    memberships = Membership.objects.filter(user=request.user).select_related('trip')
    trips = [m.trip for m in memberships]

    trip_data = []
    for trip in trips:
        balances = calculate_balances(trip)
        user_balance = balances.get(request.user.id, {}).get('balance', Decimal('0'))
        trip_data.append({
            'trip': trip,
            'balance': user_balance,
            'role': memberships.get(trip=trip).role,
        })

    return render(request, 'trips/dashboard.html', {'trip_data': trip_data})


# ─── Trip CRUD ──────────────────────────────────────────────────────────────

@login_required
def trip_create(request):
    if request.method == 'POST':
        form = TripForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                trip = form.save(commit=False)
                trip.creator = request.user
                trip.save()
                Membership.objects.create(user=request.user, trip=trip, role='organizer')
            messages.success(request, f"Voyage « {trip.name} » créé !")
            return redirect('trip_detail', pk=trip.pk)
    else:
        form = TripForm()
    return render(request, 'trips/trip_form.html', {'form': form, 'action': 'Créer'})


@login_required
def trip_detail(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    membership = get_object_or_404(Membership, trip=trip, user=request.user)

    expenses = trip.expenses.select_related('paid_by').prefetch_related('expense_splits__user')
    balances = calculate_balances(trip)
    settlements = calculate_optimized_settlements(trip)
    who_owes = calculate_who_owes_whom(trip)

    user_balance = balances.get(request.user.id, {}).get('balance', Decimal('0'))
    members = trip.get_members()

    context = {
        'trip': trip,
        'membership': membership,
        'expenses': expenses,
        'balances': balances.values(),
        'user_balance': user_balance,
        'optimized_settlements': settlements,
        'who_owes': who_owes,
        'members': members,
        'total_expenses': trip.get_total_expenses(),
        'settlement_form': SettlementForm(trip),
    }
    return render(request, 'trips/trip_detail.html', context)


@login_required
def trip_edit(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    get_object_or_404(Membership, trip=trip, user=request.user, role='organizer')

    if request.method == 'POST':
        form = TripForm(request.POST, request.FILES, instance=trip)
        if form.is_valid():
            form.save()
            messages.success(request, "Voyage mis à jour.")
            return redirect('trip_detail', pk=trip.pk)
    else:
        form = TripForm(instance=trip)
    return render(request, 'trips/trip_form.html', {'form': form, 'trip': trip, 'action': 'Modifier'})


@login_required
def trip_delete(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    get_object_or_404(Membership, trip=trip, user=request.user, role='organizer')
    if request.method == 'POST':
        trip.delete()
        messages.success(request, "Voyage supprimé.")
        return redirect('dashboard')
    return render(request, 'trips/trip_confirm_delete.html', {'trip': trip})


# ─── Join via invite link ────────────────────────────────────────────────────

@login_required
def trip_join(request, token):
    trip = get_object_or_404(Trip, invite_token=token)
    membership, created = Membership.objects.get_or_create(
        user=request.user, trip=trip,
        defaults={'role': 'member'}
    )
    if created:
        messages.success(request, f"Vous avez rejoint « {trip.name} » !")
    else:
        messages.info(request, "Vous êtes déjà membre de ce voyage.")
    return redirect('trip_detail', pk=trip.pk)


# ─── Member management ──────────────────────────────────────────────────────

@login_required
def invite_member(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    get_object_or_404(Membership, trip=trip, user=request.user, role='organizer')

    if request.method == 'POST':
        form = InviteForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                _, created = Membership.objects.get_or_create(
                    user=user, trip=trip, defaults={'role': 'member'}
                )
                if created:
                    messages.success(request, f"{user.username} ajouté au voyage.")
                else:
                    messages.warning(request, f"{user.username} est déjà membre.")
            except User.DoesNotExist:
                messages.error(request, "Aucun compte trouvé avec cet email. Partagez le lien d'invitation.")
    return redirect('trip_detail', pk=pk)


@login_required
@require_POST
def remove_member(request, pk, user_id):
    trip = get_object_or_404(Trip, pk=pk)
    get_object_or_404(Membership, trip=trip, user=request.user, role='organizer')
    if user_id != request.user.id:
        Membership.objects.filter(trip=trip, user_id=user_id).delete()
        messages.success(request, "Membre retiré du voyage.")
    return redirect('trip_detail', pk=pk)


# ─── Expenses ───────────────────────────────────────────────────────────────

@login_required
def expense_add(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    get_object_or_404(Membership, trip=trip, user=request.user)

    if request.method == 'POST':
        form = ExpenseForm(trip, request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                expense = form.save(commit=False)
                expense.trip = trip
                expense.paid_by = request.user
                expense.save()

                participants = list(form.cleaned_data['participants'])
                split_type = form.cleaned_data['split_type']

                if split_type == 'equal':
                    create_equal_splits(expense, participants)
                elif split_type == 'percentage':
                    raw = json.loads(form.cleaned_data.get('split_data') or '[]')
                    pct_data = []
                    for item in raw:
                        try:
                            u = User.objects.get(pk=item['user_id'])
                            pct_data.append({'user': u, 'percentage': Decimal(str(item['percentage']))})
                        except (User.DoesNotExist, KeyError):
                            pass
                    if pct_data:
                        create_percentage_splits(expense, pct_data)
                    else:
                        create_equal_splits(expense, participants)
                elif split_type == 'exact':
                    raw = json.loads(form.cleaned_data.get('split_data') or '[]')
                    exact_data = []
                    for item in raw:
                        try:
                            u = User.objects.get(pk=item['user_id'])
                            exact_data.append({'user': u, 'amount': Decimal(str(item['amount']))})
                        except (User.DoesNotExist, KeyError):
                            pass
                    if exact_data:
                        create_exact_splits(expense, exact_data)
                    else:
                        create_equal_splits(expense, participants)

            messages.success(request, f"Dépense « {expense.title} » ajoutée.")
            return redirect('trip_detail', pk=pk)
    else:
        form = ExpenseForm(trip)

    members = trip.get_members()
    return render(request, 'trips/expense_form.html', {'form': form, 'trip': trip, 'members': members})


@login_required
def expense_delete(request, pk, expense_pk):
    trip = get_object_or_404(Trip, pk=pk)
    expense = get_object_or_404(Expense, pk=expense_pk, trip=trip)
    membership = get_object_or_404(Membership, trip=trip, user=request.user)

    # Only payer or organizer can delete
    if expense.paid_by == request.user or membership.role == 'organizer':
        if request.method == 'POST':
            expense.delete()
            messages.success(request, "Dépense supprimée.")
            return redirect('trip_detail', pk=pk)
    else:
        messages.error(request, "Vous n'avez pas la permission de supprimer cette dépense.")
        return redirect('trip_detail', pk=pk)

    return render(request, 'trips/expense_confirm_delete.html', {'expense': expense, 'trip': trip})


# ─── Settlements ────────────────────────────────────────────────────────────

@login_required
@require_POST
def record_settlement(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    get_object_or_404(Membership, trip=trip, user=request.user)

    form = SettlementForm(trip, request.POST)
    if form.is_valid():
        settlement = form.save(commit=False)
        settlement.trip = trip
        settlement.save()
        messages.success(request, f"Règlement de {settlement.amount} {trip.currency} enregistré ✅")
    else:
        messages.error(request, "Erreur dans le formulaire de règlement.")
    return redirect('trip_detail', pk=pk)


# ─── Guest shared view ──────────────────────────────────────────────────────

def trip_summary_guest(request, token):
    """Public read-only trip summary accessible via invite token."""
    trip = get_object_or_404(Trip, invite_token=token)
    expenses = trip.expenses.select_related('paid_by').all()
    balances = calculate_balances(trip)
    settlements = calculate_optimized_settlements(trip)

    return render(request, 'trips/trip_summary_guest.html', {
        'trip': trip,
        'expenses': expenses,
        'balances': balances.values(),
        'optimized_settlements': settlements,
        'total_expenses': trip.get_total_expenses(),
    })
