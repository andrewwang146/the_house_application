# bets/services.py
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Iterable

from django.db import transaction
from django.contrib.auth import get_user_model
from .models import Wallet, Transaction, Market, Outcome, Wager, EventWallet, EventTransaction, EventMembership, MarketShare



TWOPLACES   = Decimal('0.01')
THREEPLACES = Decimal('0.001')
SIXPLACES   = Decimal('0.000001')

class OddsResult(dict):
    pass


def _adjust_display_odds(raw: Decimal) -> Decimal:
    if raw >= Decimal('1.01'):
        return raw.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    r = max(raw, Decimal('1.001'))

    x = float((r - Decimal('1.0')) / Decimal('0.01'))
    x = min(max(x, 0.0), 0.999999)

    alpha = 3.0
    y = math.log1p(alpha * x) / math.log1p(alpha)

    val = 1.001 + 0.009 * y 
    return Decimal(str(val)).quantize(THREEPLACES, rounding=ROUND_HALF_UP)


def compute_odds(weights: Iterable[int], margin: Decimal) -> OddsResult:
    ws = [Decimal(max(0, int(w))) for w in weights]
    total = sum(ws)
    if not ws:
        return OddsResult()
    if total == 0:
        ws = [Decimal(1) for _ in ws]; total = sum(ws)

    m = Decimal(margin)
    overround = (Decimal(1) + m)
    out: OddsResult = OddsResult()
    for i, w in enumerate(ws):
        p = (w / total)
        p_prime = (p * overround).quantize(SIXPLACES)
        if p_prime == 0:
            odds = Decimal('999.990')
        else:
            raw_odds = (Decimal(1) / p_prime)
            odds = _adjust_display_odds(raw_odds)
        out[i] = { 'prob': p_prime, 'odds': odds }
    return out


User = get_user_model()

def can_view_market(user, market):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user == market.creator or user == market.house:
        return True
    if market.event:
        if EventMembership.objects.filter(event=market.event, user=user).exists():
            return True
    if MarketShare.objects.filter(market=market, user=user).exists():
        return True
    return False


# --- Wallet & wagering -------------------------------------------------------

def ensure_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet

def ensure_event_wallet(event):
    wallet, _ = EventWallet.objects.get_or_create(event=event)
    return wallet

@transaction.atomic
def deposit(user, amount: Decimal, note: str = ""):
    wallet = ensure_wallet(user)
    wallet.balance += amount
    wallet.save(update_fields=['balance'])
    Transaction.objects.create(user=user, amount=amount, type=Transaction.DEPOSIT, note=note)
    return wallet.balance

@transaction.atomic
def place_wager(user, outcome: Outcome, stake: Decimal):
    wallet = ensure_wallet(user)
    if stake <= 0:
        raise ValueError("Stake must be positive")
    if wallet.balance < stake:
        raise ValueError("Insufficient balance")

    wallet.balance -= stake; wallet.save(update_fields=['balance'])
    Transaction.objects.create(
        user=user, amount=-stake, type=Transaction.WAGER_STAKE,
        note=f"Stake on {outcome.market.title}: {outcome.title}"
    )
    potential = (stake * outcome.decimal_odds).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    w = Wager.objects.create(
        user=user, market=outcome.market, outcome=outcome,
        stake=stake, odds_at_placement=outcome.decimal_odds,
        potential_payout=potential,
    )
    return w

@transaction.atomic
def settle_market(market: Market, winning_outcome: Outcome):
    if market.status == Market.SETTLED:
        return

    # mark winner
    for oc in market.outcomes.all():
        oc.is_winner = (oc.id == winning_outcome.id)
        oc.save(update_fields=['is_winner'])

    total_staked = Decimal('0.00')
    total_payout = Decimal('0.00')

    for w in market.wagers.select_related('outcome').all():
        total_staked += w.stake
        if w.outcome_id == winning_outcome.id:
            payout = (w.stake * w.odds_at_placement).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            total_payout += payout
            wallet = ensure_wallet(w.user)
            wallet.balance += payout
            wallet.save(update_fields=['balance'])
            Transaction.objects.create(
                user=w.user,
                amount=payout,
                type=Transaction.WAGER_PAYOUT,
                note=f"Win: {market.title}",
            )
        w.status = Wager.PAID
        w.save(update_fields=['status'])

    house_user = market.house

    house_delta = (total_staked - total_payout).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if house_user and house_delta != 0:
        wallet = ensure_wallet(house_user)
        wallet.balance += house_delta
        wallet.save(update_fields=['balance'])
        Transaction.objects.create(
            user=house_user,
            amount=house_delta,
            type=Transaction.HOUSE_COMMISSION,
            note=f"Settlement: {market.title}",
        )

    elif market.event and house_delta != 0:
        ewallet = ensure_event_wallet(market.event)
        ewallet.balance += house_delta
        ewallet.save(update_fields=['balance'])
        EventTransaction.objects.create(
            event=market.event,
            amount=house_delta,
            type=EventTransaction.TREASURY_CREDIT if house_delta > 0 else EventTransaction.TREASURY_DEBIT,
            note=f"Settlement: {market.title}",
        )

    market.status = Market.SETTLED
    market.save(update_fields=['status'])
