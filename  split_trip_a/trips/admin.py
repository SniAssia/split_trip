from django.contrib import admin
from .models import Trip, Membership, Expense, ExpenseSplit, Settlement


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ['name', 'creator', 'currency', 'start_date', 'end_date', 'get_member_count', 'get_expense_count']
    list_filter = ['currency']
    search_fields = ['name', 'creator__username']
    readonly_fields = ['invite_token']


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'trip', 'role', 'joined_at']
    list_filter = ['role']


class ExpenseSplitInline(admin.TabularInline):
    model = ExpenseSplit
    extra = 0


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'trip', 'paid_by', 'amount', 'category', 'split_type', 'date']
    list_filter = ['category', 'split_type', 'trip']
    inlines = [ExpenseSplitInline]


@admin.register(ExpenseSplit)
class ExpenseSplitAdmin(admin.ModelAdmin):
    list_display = ['expense', 'user', 'amount_owed']


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ['trip', 'payer', 'receiver', 'amount', 'settled_at']
