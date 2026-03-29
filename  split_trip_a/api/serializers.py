from rest_framework import serializers
from django.contrib.auth.models import User
from trips.models import Trip, Membership, Expense, ExpenseSplit, Settlement


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ['id', 'user', 'role', 'joined_at']


class ExpenseSplitSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ['id', 'user', 'amount_owed', 'percentage']


class ExpenseSerializer(serializers.ModelSerializer):
    paid_by = UserSerializer(read_only=True)
    expense_splits = ExpenseSplitSerializer(many=True, read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    split_type_display = serializers.CharField(source='get_split_type_display', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'title', 'amount', 'category', 'category_display',
            'split_type', 'split_type_display', 'date', 'notes',
            'paid_by', 'expense_splits', 'created_at',
        ]


class ExpenseCreateSerializer(serializers.ModelSerializer):
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True
    )
    split_data = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False
    )

    class Meta:
        model = Expense
        fields = ['title', 'amount', 'category', 'split_type', 'date', 'notes',
                  'participant_ids', 'split_data']


class TripSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    memberships = MembershipSerializer(many=True, read_only=True)
    total_expenses = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    expense_count = serializers.SerializerMethodField()
    currency_display = serializers.CharField(source='get_currency_display', read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id', 'name', 'description', 'currency', 'currency_display',
            'start_date', 'end_date', 'creator', 'memberships',
            'total_expenses', 'member_count', 'expense_count',
            'invite_token', 'created_at',
        ]

    def get_total_expenses(self, obj):
        return obj.get_total_expenses()

    def get_member_count(self, obj):
        return obj.get_member_count()

    def get_expense_count(self, obj):
        return obj.get_expense_count()


class TripCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['name', 'description', 'currency', 'start_date', 'end_date']

    def validate(self, data):
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError("La date de fin doit être après la date de début.")
        return data


class SettlementSerializer(serializers.ModelSerializer):
    payer = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)

    class Meta:
        model = Settlement
        fields = ['id', 'payer', 'receiver', 'amount', 'notes', 'settled_at']


class BalanceSerializer(serializers.Serializer):
    user = UserSerializer()
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)


class OptimizedSettlementSerializer(serializers.Serializer):
    payer = UserSerializer()
    receiver = UserSerializer()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
