from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from .models import Event, Market, UserSettings

User = get_user_model()

class DepositForm(forms.Form):
    amount = forms.DecimalField(min_value=1, decimal_places=2, max_digits=12)

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'description', 'default_house']

class MarketForm(forms.ModelForm):
    be_the_house = forms.BooleanField(required=False, initial=True, help_text="If checked, you will act as the house.")
    house = forms.ModelChoiceField(queryset=User.objects.all(), required=False, help_text="Optional override.")
    max_bet_limit = forms.DecimalField(min_value=Decimal('0.01'), decimal_places=2, max_digits=12)

    class Meta:
        model = Market
        fields = ['title', 'event', 'house_margin', 'closes_at', 'house', 'max_bet_limit']
        widgets = {
            'closes_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['closes_at'].input_formats = ['%Y-%m-%dT%H:%M']

        default = Decimal('100.00')
        if user is not None:
            us = UserSettings.objects.filter(user=user).only('default_max_bet_limit').first()
            if us:
                default = us.default_max_bet_limit
        self.fields['max_bet_limit'].initial = default


class UserLookupForm(forms.Form):
    query = forms.CharField(label="Username or email", max_length=150)

class EventInviteForm(UserLookupForm):
    pass

class MarketShareForm(UserLookupForm):
    pass
