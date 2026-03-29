from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/register/', views.register, name='register'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Trips
    path('trips/create/', views.trip_create, name='trip_create'),
    path('trips/<int:pk>/', views.trip_detail, name='trip_detail'),
    path('trips/<int:pk>/edit/', views.trip_edit, name='trip_edit'),
    path('trips/<int:pk>/delete/', views.trip_delete, name='trip_delete'),
    path('trips/join/<uuid:token>/', views.trip_join, name='trip_join'),
    path('trips/summary/<uuid:token>/', views.trip_summary_guest, name='trip_summary_guest'),

    # Members
    path('trips/<int:pk>/invite/', views.invite_member, name='invite_member'),
    path('trips/<int:pk>/members/<int:user_id>/remove/', views.remove_member, name='remove_member'),

    # Expenses
    path('trips/<int:pk>/expenses/add/', views.expense_add, name='expense_add'),
    path('trips/<int:pk>/expenses/<int:expense_pk>/delete/', views.expense_delete, name='expense_delete'),

    # Settlements
    path('trips/<int:pk>/settlements/record/', views.record_settlement, name='record_settlement'),
]
