from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Trip, Expense, ExpenseSplit, Settlement, SPLIT_CHOICES


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ['name', 'description', 'currency', 'start_date', 'end_date', 'cover_image']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError("La date de fin doit être après la date de début.")
        return cleaned


class ExpenseForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Participants"
    )
    # For percentage/exact splits — raw JSON handled in view
    split_data = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Expense
        fields = ['title', 'amount', 'category', 'split_type', 'date', 'receipt', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, trip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        members = trip.get_members()
        self.fields['participants'].queryset = members
        self.fields['participants'].initial = members


class InviteForm(forms.Form):
    email = forms.EmailField(label="Adresse email du membre")


class SettlementForm(forms.ModelForm):
    class Meta:
        model = Settlement
        fields = ['payer', 'receiver', 'amount', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, trip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        members = trip.get_members()
        self.fields['payer'].queryset = members
        self.fields['receiver'].queryset = members
