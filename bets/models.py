from __future__ import annotations
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


User = settings.AUTH_USER_MODEL


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))


def __str__(self):
    return f"Wallet({self.user}, balance={self.balance})"


class Transaction(models.Model):
    DEPOSIT = 'DEPOSIT'
    WITHDRAW = 'WITHDRAW'
    WAGER_STAKE = 'WAGER_STAKE'
    WAGER_PAYOUT = 'WAGER_PAYOUT'
    HOUSE_COMMISSION = 'HOUSE_COMMISSION'
    TYPES = [
        (DEPOSIT, 'Deposit'),
        (WITHDRAW, 'Withdraw'),
        (WAGER_STAKE, 'Wager Stake'),
        (WAGER_PAYOUT, 'Wager Payout'),
        (HOUSE_COMMISSION, 'House Commission/Settlement'),
    ]


    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=32, choices=TYPES)
    created_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True)


    class Meta:
      ordering = ['-created_at']

class Event(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_events')
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    default_house = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='events_as_default_house'
    )

    def __str__(self):
        return self.name

class EventWallet(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"EventWallet({self.event.name}, balance={self.balance})"


class EventTransaction(models.Model):
    TREASURY_CREDIT = 'TREASURY_CREDIT'  # positive → house surplus
    TREASURY_DEBIT  = 'TREASURY_DEBIT'   # negative → house deficit
    TYPES = [
        (TREASURY_CREDIT, 'Treasury Credit'),
        (TREASURY_DEBIT,  'Treasury Debit'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=32, choices=TYPES)
    created_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event.name} {self.type} {self.amount} @ {self.created_at:%Y-%m-%d %H:%M}"


class EventMembership(models.Model):
    MEMBER = 'MEMBER'
    ADMIN  = 'ADMIN'
    ROLES = [(MEMBER, 'Member'), (ADMIN, 'Admin')]

    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_memberships')
    role = models.CharField(max_length=10, choices=ROLES, default=MEMBER)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='added_event_members')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('event', 'user')


class EventInvite(models.Model):
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    DECLINED = 'DECLINED'
    STATUSES = [(PENDING,'Pending'),(ACCEPTED,'Accepted'),(DECLINED,'Declined')]

    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='invites')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_invites_sent')
    to_user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_invites_received')
    status    = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    seen      = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('event', 'to_user', 'status')


class Market(models.Model):
    OPEN = 'OPEN'
    SUSPENDED = 'SUSPENDED'
    SETTLED = 'SETTLED'
    STATUSES = [(OPEN,'Open'),(SUSPENDED,'Suspended'),(SETTLED,'Settled')]

    title = models.CharField(max_length=200)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_markets')
    house = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='house_markets')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True, related_name='markets')
    house_margin = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.05'))
    status = models.CharField(max_length=12, choices=STATUSES, default=OPEN)
    closes_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    max_bet_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100.00'))

    def __str__(self):
        return self.title

    @property
    def is_closed(self) -> bool:
        return bool(self.closes_at and timezone.now() >= self.closes_at)


class MarketShare(models.Model):
    market = models.ForeignKey('Market', on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_markets')
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='added_market_shares')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('market', 'user')


class MarketShareRequest(models.Model):
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    DECLINED = 'DECLINED'
    STATUSES = [(PENDING,'Pending'),(ACCEPTED,'Accepted'),(DECLINED,'Declined')]

    market = models.ForeignKey('Market', on_delete=models.CASCADE, related_name='share_requests')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='market_share_requests_sent')
    to_user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='market_share_requests_received')
    status    = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    seen      = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('market', 'to_user', 'status')


class Outcome(models.Model):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='outcomes')
    title = models.CharField(max_length=120)
    slider_weight = models.PositiveIntegerField(default=0) # 0‑100 as set by creator
    implied_probability = models.DecimalField(max_digits=8, decimal_places=6, default=Decimal('0')) # after normalization×(1+m)
    decimal_odds = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.00'))
    is_winner = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.title} ({self.decimal_odds})"


class Wager(models.Model):
    PLACED = 'PLACED'
    CANCELLED = 'CANCELLED'
    PAID = 'PAID'
    STATUSES = [(PLACED,'Placed'),(CANCELLED,'Cancelled'),(PAID,'Paid')]


    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wagers')
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='wagers')
    outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, related_name='wagers')
    stake = models.DecimalField(max_digits=12, decimal_places=2)
    odds_at_placement = models.DecimalField(max_digits=8, decimal_places=3)
    potential_payout = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=STATUSES, default=PLACED)
    placed_at = models.DateTimeField(default=timezone.now)


    class Meta:
        ordering = ['-placed_at']

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    default_max_bet_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100.00'))

    def __str__(self):
        return f"UserSettings({self.user}, default_max_bet_limit={self.default_max_bet_limit})"
    

class Friendship(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friends_from')
    friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friends_to')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'friend')

class FriendshipRequest(models.Model):
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    DECLINED = 'DECLINED'
    STATUSES = [(PENDING,'Pending'),(ACCEPTED,'Accepted'),(DECLINED,'Declined')]

    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_requests_sent')
    to_user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_requests_received')
    status    = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    seen      = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('from_user', 'to_user', 'status')
