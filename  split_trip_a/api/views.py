from decimal import Decimal
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from trips.models import Trip, Membership, Expense, ExpenseSplit, Settlement
from trips.services import (
    calculate_balances, calculate_optimized_settlements, calculate_who_owes_whom,
    create_equal_splits, create_percentage_splits, create_exact_splits,
)
from .serializers import (
    TripSerializer, TripCreateSerializer, ExpenseSerializer, ExpenseCreateSerializer,
    BalanceSerializer, OptimizedSettlementSerializer, MembershipSerializer,
    SettlementSerializer, UserSerializer,
)


class IsTripMember(permissions.BasePermission):
    def has_permission(self, request, view):
        trip_pk = view.kwargs.get('pk')
        return Membership.objects.filter(trip_id=trip_pk, user=request.user).exists()


class IsTripOrganizer(permissions.BasePermission):
    def has_permission(self, request, view):
        trip_pk = view.kwargs.get('pk')
        return Membership.objects.filter(trip_id=trip_pk, user=request.user, role='organizer').exists()


# ─── Trip endpoints ──────────────────────────────────────────────────────────

class TripListCreateView(generics.ListCreateAPIView):
    """GET /api/trips/ — List user's trips | POST — Create trip"""

    def get_serializer_class(self):
        return TripCreateSerializer if self.request.method == 'POST' else TripSerializer

    def get_queryset(self):
        return Trip.objects.filter(memberships__user=self.request.user)

    def perform_create(self, serializer):
        with transaction.atomic():
            trip = serializer.save(creator=self.request.user)
            Membership.objects.create(user=self.request.user, trip=trip, role='organizer')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        trip = Trip.objects.get(pk=serializer.instance.pk)
        return Response(TripSerializer(trip).data, status=status.HTTP_201_CREATED)


class TripDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/trips/{id}/"""

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [permissions.IsAuthenticated(), IsTripOrganizer()]
        return [permissions.IsAuthenticated(), IsTripMember()]

    def get_queryset(self):
        return Trip.objects.filter(memberships__user=self.request.user)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return TripCreateSerializer
        return TripSerializer


# ─── Expense endpoints ───────────────────────────────────────────────────────

class ExpenseListCreateView(APIView):
    """GET /api/trips/{id}/expenses/ | POST — Add expense"""
    permission_classes = [permissions.IsAuthenticated, IsTripMember]

    def get(self, request, pk):
        trip = Trip.objects.get(pk=pk)
        expenses = trip.expenses.select_related('paid_by').prefetch_related('expense_splits__user')
        return Response(ExpenseSerializer(expenses, many=True).data)

    def post(self, request, pk):
        trip = Trip.objects.get(pk=pk)
        serializer = ExpenseCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        with transaction.atomic():
            expense = Expense.objects.create(
                trip=trip,
                paid_by=request.user,
                title=data['title'],
                amount=data['amount'],
                category=data['category'],
                split_type=data['split_type'],
                date=data.get('date'),
                notes=data.get('notes', ''),
            )

            participant_ids = data.get('participant_ids', [])
            participants = list(User.objects.filter(id__in=participant_ids))

            split_type = data['split_type']
            split_data = data.get('split_data', [])

            if split_type == 'equal':
                create_equal_splits(expense, participants)
            elif split_type == 'percentage':
                pct_data = []
                for item in split_data:
                    try:
                        u = User.objects.get(pk=item['user_id'])
                        pct_data.append({'user': u, 'percentage': Decimal(str(item['percentage']))})
                    except (User.DoesNotExist, KeyError):
                        pass
                create_percentage_splits(expense, pct_data) if pct_data else create_equal_splits(expense, participants)
            elif split_type == 'exact':
                exact_data = []
                for item in split_data:
                    try:
                        u = User.objects.get(pk=item['user_id'])
                        exact_data.append({'user': u, 'amount': Decimal(str(item['amount']))})
                    except (User.DoesNotExist, KeyError):
                        pass
                create_exact_splits(expense, exact_data) if exact_data else create_equal_splits(expense, participants)

        return Response(ExpenseSerializer(expense).data, status=status.HTTP_201_CREATED)


class ExpenseDeleteView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTripMember]

    def get_queryset(self):
        return Expense.objects.filter(trip_id=self.kwargs['pk'])

    def get_object(self):
        return Expense.objects.get(pk=self.kwargs['expense_pk'], trip_id=self.kwargs['pk'])


# ─── Balance endpoints ───────────────────────────────────────────────────────

class BalanceView(APIView):
    """GET /api/trips/{id}/balances/"""
    permission_classes = [permissions.IsAuthenticated, IsTripMember]

    def get(self, request, pk):
        trip = Trip.objects.get(pk=pk)
        balances = calculate_balances(trip)
        result = [{'user': v['user'], 'balance': v['balance']} for v in balances.values()]
        return Response(BalanceSerializer(result, many=True).data)


class SettlementPlanView(APIView):
    """GET /api/trips/{id}/settlements/"""
    permission_classes = [permissions.IsAuthenticated, IsTripMember]

    def get(self, request, pk):
        trip = Trip.objects.get(pk=pk)
        settlements = calculate_optimized_settlements(trip)
        who_owes = calculate_who_owes_whom(trip)

        return Response({
            'optimized_settlements': OptimizedSettlementSerializer(settlements, many=True).data,
            'who_owes_whom': [
                {
                    'from': UserSerializer(d['from']).data,
                    'to': UserSerializer(d['to']).data,
                    'amount': d['amount'],
                }
                for d in who_owes
            ]
        })


# ─── Invite endpoint ─────────────────────────────────────────────────────────

class InviteMemberView(APIView):
    """POST /api/trips/{id}/invite/"""
    permission_classes = [permissions.IsAuthenticated, IsTripOrganizer]

    def post(self, request, pk):
        trip = Trip.objects.get(pk=pk)
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email requis.'}, status=400)
        try:
            user = User.objects.get(email=email)
            _, created = Membership.objects.get_or_create(user=user, trip=trip, defaults={'role': 'member'})
            return Response({
                'message': 'Membre ajouté.' if created else 'Déjà membre.',
                'membership': MembershipSerializer(Membership.objects.get(user=user, trip=trip)).data,
            })
        except User.DoesNotExist:
            return Response({
                'error': 'Aucun utilisateur trouvé.',
                'invite_link': request.build_absolute_uri(f'/trips/join/{trip.invite_token}/'),
            }, status=404)


# ─── Members endpoint ────────────────────────────────────────────────────────

class MemberListView(APIView):
    """GET /api/trips/{id}/members/"""
    permission_classes = [permissions.IsAuthenticated, IsTripMember]

    def get(self, request, pk):
        memberships = Membership.objects.filter(trip_id=pk).select_related('user')
        return Response(MembershipSerializer(memberships, many=True).data)


# ─── Record settlement ───────────────────────────────────────────────────────

class RecordSettlementView(APIView):
    """POST /api/trips/{id}/settlements/record/"""
    permission_classes = [permissions.IsAuthenticated, IsTripMember]

    def post(self, request, pk):
        trip = Trip.objects.get(pk=pk)
        payer_id = request.data.get('payer_id')
        receiver_id = request.data.get('receiver_id')
        amount = request.data.get('amount')
        notes = request.data.get('notes', '')

        try:
            payer = User.objects.get(pk=payer_id)
            receiver = User.objects.get(pk=receiver_id)
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable.'}, status=400)

        settlement = Settlement.objects.create(
            trip=trip, payer=payer, receiver=receiver,
            amount=Decimal(str(amount)), notes=notes,
        )
        return Response(SettlementSerializer(settlement).data, status=status.HTTP_201_CREATED)
