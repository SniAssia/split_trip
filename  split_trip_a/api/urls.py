from django.urls import path
from . import views

urlpatterns = [
    # Trips
    path('trips/', views.TripListCreateView.as_view(), name='api_trip_list'),
    path('trips/<int:pk>/', views.TripDetailView.as_view(), name='api_trip_detail'),

    # Expenses
    path('trips/<int:pk>/expenses/', views.ExpenseListCreateView.as_view(), name='api_expense_list'),
    path('trips/<int:pk>/expenses/<int:expense_pk>/', views.ExpenseDeleteView.as_view(), name='api_expense_delete'),

    # Balances & Settlements
    path('trips/<int:pk>/balances/', views.BalanceView.as_view(), name='api_balances'),
    path('trips/<int:pk>/settlements/', views.SettlementPlanView.as_view(), name='api_settlements'),
    path('trips/<int:pk>/settlements/record/', views.RecordSettlementView.as_view(), name='api_record_settlement'),

    # Members
    path('trips/<int:pk>/members/', views.MemberListView.as_view(), name='api_members'),
    path('trips/<int:pk>/invite/', views.InviteMemberView.as_view(), name='api_invite'),
]
