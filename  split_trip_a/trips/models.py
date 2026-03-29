import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


CURRENCY_CHOICES = [
    ('MAD', 'Dirham marocain (MAD)'),
    ('EUR', 'Euro (EUR)'),
    ('USD', 'Dollar américain (USD)'),
    ('GBP', 'Livre sterling (GBP)'),
]

ROLE_CHOICES = [
    ('organizer', 'Organisateur'),
    ('member', 'Membre'),
    ('guest', 'Invité'),
]

CATEGORY_CHOICES = [
    ('food', '🍽️ Nourriture'),
    ('transport', '🚗 Transport'),
    ('accommodation', '🏨 Hébergement'),
    ('activities', '🎭 Activités'),
    ('shopping', '🛍️ Shopping'),
    ('health', '💊 Santé'),
    ('other', '📦 Autre'),
]

SPLIT_CHOICES = [
    ('equal', 'Égal'),
    ('percentage', 'Pourcentage'),
    ('exact', 'Montant exact'),
]


class Trip(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nom du voyage")
    description = models.TextField(blank=True, verbose_name="Description")
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_trips')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='MAD')
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    cover_image = models.ImageField(upload_to='trip_covers/', blank=True, null=True)
    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Voyage"
        verbose_name_plural = "Voyages"

    def __str__(self):
        return self.name

    def get_invite_link(self):
        return f"/trips/join/{self.invite_token}/"

    def get_total_expenses(self):
        return self.expenses.aggregate(total=models.Sum('amount'))['total'] or 0

    def get_members(self):
        return User.objects.filter(memberships__trip=self)

    def get_member_count(self):
        return self.memberships.count()

    def get_expense_count(self):
        return self.expenses.count()

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1


class Membership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'trip')
        verbose_name = "Membership"
        verbose_name_plural = "Memberships"

    def __str__(self):
        return f"{self.user.username} → {self.trip.name} ({self.role})"

    def is_organizer(self):
        return self.role == 'organizer'


class Expense(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='expenses')
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paid_expenses')
    title = models.CharField(max_length=200, verbose_name="Description")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    split_type = models.CharField(max_length=20, choices=SPLIT_CHOICES, default='equal')
    date = models.DateField(default=timezone.now, verbose_name="Date")
    receipt = models.ImageField(upload_to='receipts/', blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"

    def __str__(self):
        return f"{self.title} – {self.amount} {self.trip.currency}"

    def get_participants(self):
        return User.objects.filter(expense_splits__expense=self)

    def get_category_display_icon(self):
        icons = {
            'food': '🍽️', 'transport': '🚗', 'accommodation': '🏨',
            'activities': '🎭', 'shopping': '🛍️', 'health': '💊', 'other': '📦',
        }
        return icons.get(self.category, '📦')


class ExpenseSplit(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='expense_splits')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expense_splits')
    amount_owed = models.DecimalField(max_digits=10, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('expense', 'user')
        verbose_name = "Répartition"
        verbose_name_plural = "Répartitions"

    def __str__(self):
        return f"{self.user.username} doit {self.amount_owed} pour {self.expense.title}"


class Settlement(models.Model):
    """Records an actual payment made between two members."""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='settlements')
    payer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='settlements_paid')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='settlements_received')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    settled_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-settled_at']
        verbose_name = "Règlement"
        verbose_name_plural = "Règlements"

    def __str__(self):
        return f"{self.payer.username} → {self.receiver.username}: {self.amount}"
