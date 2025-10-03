# bets/views.py
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import get_user_model, logout
User = get_user_model()
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.views.decorators.http import require_POST

from .forms import DepositForm, EventForm, MarketForm, EventInviteForm, MarketShareForm, UserLookupForm
from .services import ensure_wallet, deposit as do_deposit, compute_odds, place_wager, settle_market, can_view_market
from .models import (
    Event, Market, Outcome, Wager, UserSettings,
    Friendship, FriendshipRequest,
    EventWallet,
    EventMembership, EventInvite,
    MarketShare, MarketShareRequest
)

TWOPLACES = Decimal('0.01')

@login_required
def dashboard(request):
    wallet = ensure_wallet(request.user)

    member_event_ids = EventMembership.objects.filter(user=request.user).values_list('event_id', flat=True)
    events_for_you = (
        Event.objects.filter(Q(creator=request.user) | Q(id__in=member_event_ids))
        .order_by('-created_at')[:10]
    )

    your_markets = (
    Market.objects
    .filter(Q(creator=request.user) | Q(house=request.user))
    .exclude(status=Market.SETTLED)
    .select_related('event')
    .order_by('-created_at')[:10]
)

    now = timezone.now()
    shared_ids = MarketShare.objects.filter(user=request.user).values_list('market_id', flat=True)
    open_markets = (
        Market.objects.filter(status=Market.OPEN)
        .filter(Q(event_id__in=member_event_ids) | Q(id__in=shared_ids))
        .filter(Q(closes_at__isnull=True) | Q(closes_at__gt=now))
        .exclude(creator=request.user)
        .exclude(house=request.user)
        .select_related('event', 'creator')
        .order_by('-created_at')[:10]
    )

    settled_preview = (
        Market.objects.filter(creator=request.user, status=Market.SETTLED)
        .order_by('-created_at')
        .prefetch_related('outcomes')[:3]
    )

    return render(request, 'bets/dashboard.html', {
        'wallet': wallet,
        'events': events_for_you,
        'your_markets': your_markets,
        'open_markets': open_markets,
        'settled_preview': settled_preview,
        'deposit_form': DepositForm(),
    })

@login_required
def deposit_view(request):
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            amt = form.cleaned_data['amount']
            do_deposit(request.user, amt, note='User deposit (fake money)')
            messages.success(request, f"Deposited {amt} (fake currency).")
    return redirect('bets:dashboard')


# --- Event functions -------------------------------------------------------


@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            ev: Event = form.save(commit=False)
            ev.creator = request.user
            ev.save()
            messages.success(request, 'Event created.')
            return redirect('bets:event_detail', pk=ev.pk)
    else:
        form = EventForm()
    return render(request, 'bets/event_create.html', {'form': form})


@login_required
def event_detail(request, pk: int):
    ev = get_object_or_404(Event, pk=pk)

    is_member = EventMembership.objects.filter(event=ev, user=request.user).exists()
    can_view = (request.user == ev.creator) or is_member or request.user.is_superuser
    if not can_view:
        messages.error(request, "You don’t have access to this event.")
        return redirect('bets:dashboard')

    can_invite = (
        request.user == ev.creator or
        EventMembership.objects.filter(event=ev, user=request.user, role=EventMembership.ADMIN).exists() or
        request.user.is_superuser
    )

    invite_form = EventInviteForm()

    members = (
        EventMembership.objects.filter(event=ev)
        .select_related('user')
        .order_by('user__username')
    )
    member_users = [m.user for m in members]

    markets = ev.markets.select_related('creator', 'house').order_by('-created_at')

    return render(request, 'bets/event_detail.html', {
        'event': ev,
        'invite_form': invite_form,
        'members': member_users,
        'can_invite': can_invite,
        'markets': markets,
    })


@login_required
def event_invite(request, pk: int):
    ev = get_object_or_404(Event, pk=pk)
    is_admin = (request.user == ev.creator) or EventMembership.objects.filter(event=ev, user=request.user, role=EventMembership.ADMIN).exists()
    if not is_admin:
        messages.error(request, "You don’t have permission to invite to this event.")
        return redirect('bets:event_detail', pk=pk)

    if request.method == 'POST':
        form = EventInviteForm(request.POST)
        if form.is_valid():
            q = form.cleaned_data['query'].strip()
            u = User.objects.filter(username__iexact=q).first() or User.objects.filter(email__iexact=q).first()
            if not u:
                messages.error(request, "User not found.")
            elif EventMembership.objects.filter(event=ev, user=u).exists():
                messages.info(request, f"{u.username} is already a member.")
            elif EventInvite.objects.filter(event=ev, to_user=u, status=EventInvite.PENDING).exists():
                messages.info(request, "Invite already pending.")
            else:
                EventInvite.objects.create(event=ev, from_user=request.user, to_user=u, seen=False)
                messages.success(request, f"Invite sent to {u.username}.")
            return redirect('bets:event_detail', pk=pk)
    else:
        form = EventInviteForm()

    members = User.objects.filter(event_memberships__event=ev).distinct()
    pending = EventInvite.objects.filter(event=ev, status=EventInvite.PENDING)
    return render(request, 'bets/event_detail.html', {'event': ev, 'invite_form': form, 'members': members, 'pending_invites': pending})


@login_required
@require_POST
def event_invite_accept(request, invite_id: int):
    inv = get_object_or_404(EventInvite, pk=invite_id, to_user=request.user, status=EventInvite.PENDING)
    EventMembership.objects.get_or_create(event=inv.event, user=request.user, defaults={'role': EventMembership.MEMBER, 'added_by': inv.from_user})
    inv.status = EventInvite.ACCEPTED; inv.save(update_fields=['status'])
    messages.success(request, f"Joined event: {inv.event.name}")
    return redirect('bets:dashboard')


@login_required
@require_POST
def event_invite_decline(request, invite_id: int):
    inv = get_object_or_404(EventInvite, pk=invite_id, to_user=request.user, status=EventInvite.PENDING)
    inv.status = EventInvite.DECLINED; inv.save(update_fields=['status'])
    messages.info(request, "Invite declined.")
    return redirect('bets:dashboard')


@login_required
@require_POST
def event_remove_member(request, pk: int, user_id: int):
    ev = get_object_or_404(Event, pk=pk)

    is_admin = (request.user == ev.creator) or EventMembership.objects.filter(event=ev, user=request.user, role=EventMembership.ADMIN).exists()
    if not is_admin:
        messages.error(request, "You don’t have permission to remove members.")
        return redirect('bets:event_detail', pk=pk)

    target = get_object_or_404(User, pk=user_id)
    if target == ev.creator:
        messages.error(request, "You can’t remove the event creator.")
        return redirect('bets:event_detail', pk=pk)

    from .models import Market
    active_bet_exists = Wager.objects.filter(
        user=target,
        market__event=ev,
        market__status__in=[Market.OPEN, Market.SUSPENDED]
    ).exists()
    if active_bet_exists:
        messages.error(request, "Cannot remove: user has active bets in this event.")
        return redirect('bets:event_detail', pk=pk)

    EventMembership.objects.filter(event=ev, user=target).delete()
    messages.success(request, f"Removed {target.username} from the event.")
    return redirect('bets:event_detail', pk=pk)


# --- Market functions -------------------------------------------------------


@login_required
@transaction.atomic
def market_create(request):
    if request.method == 'POST':
        form = MarketForm(request.POST, user=request.user)
        if form.is_valid():
            mkt: Market = form.save(commit=False)
            mkt.creator = request.user

            selected_event = form.cleaned_data.get('event')
            selected_house = form.cleaned_data.get('house')
            be_the_house  = form.cleaned_data.get('be_the_house') is True

            if be_the_house:
                mkt.house = request.user
            elif selected_house:
                mkt.house = selected_house
            elif selected_event and getattr(selected_event, 'default_house', None):
                mkt.house = selected_event.default_house
            else:
                mkt.house = None

            mkt.max_bet_limit = form.cleaned_data['max_bet_limit']
            mkt.save()

            if request.POST.get('set_default_max_bet') == '1':
                us, _ = UserSettings.objects.get_or_create(user=request.user)
                us.default_max_bet_limit = mkt.max_bet_limit
                us.save(update_fields=['default_max_bet_limit'])
                messages.success(request, f"Saved {mkt.max_bet_limit} as your new default max bet for future markets.")

            weights, rows, i = [], [], 0
            while True:
                title = request.POST.get(f'outcomes[{i}][title]')
                weight = request.POST.get(f'outcomes[{i}][weight]')
                if title is None and weight is None:
                    break
                if title and weight is not None:
                    try:
                        w = int(weight)
                    except (TypeError, ValueError):
                        w = 0
                    w = max(0, min(100, w))
                    rows.append((title.strip(), w))
                    weights.append(w)
                i += 1

            if len(rows) < 2:
                messages.error(request, 'Please provide at least two outcomes.')
                mkt.delete()
                return render(request, 'bets/market_create.html', {'form': form, 'current_default_max': form.fields['max_bet_limit'].initial})

            odds = compute_odds(weights, Decimal(mkt.house_margin))
            for idx, (title, w) in enumerate(rows):
                res = odds[idx]
                Outcome.objects.create(
                    market=mkt,
                    title=title,
                    slider_weight=w,
                    implied_probability=res['prob'],
                    decimal_odds=res['odds'],
                )

            messages.success(request, 'Market created.')
            return redirect('bets:market_detail', pk=mkt.pk)
    else:
        form = MarketForm(user=request.user)

    return render(request, 'bets/market_create.html', {'form': form, 'current_default_max': form.fields['max_bet_limit'].initial})

@require_POST
@login_required
def market_settle(request, pk: int):
    mkt = get_object_or_404(Market, pk=pk)

    if not (request.user == mkt.creator or request.user == mkt.house or request.user.is_superuser):
      messages.error(request, "You don’t have permission to settle this market.")
      return redirect('bets:market_detail', pk=mkt.pk)

    if mkt.status != Market.OPEN:
      messages.error(request, "Only open markets can be settled.")
      return redirect('bets:market_detail', pk=mkt.pk)

    winner_id = request.POST.get('winner_id')
    try:
      winner = mkt.outcomes.get(pk=int(winner_id))
    except Exception:
      messages.error(request, "Please select a valid winning outcome.")
      return redirect('bets:market_detail', pk=mkt.pk)

    try:
      settle_market(mkt, winner)
      messages.success(request, f"Settled: '{winner.title}' wins.")
    except Exception as e:
      messages.error(request, f"Settlement failed: {e}")

    return redirect('bets:market_detail', pk=mkt.pk)


@login_required
def market_settle(request, pk: int):
    mkt = get_object_or_404(Market, pk=pk)
    if request.user != mkt.creator and request.user != mkt.house and not request.user.is_superuser:
        messages.error(request, 'Only the market creator or house can settle this market.')
        return redirect('bets:market_detail', pk=mkt.pk)

    if request.method == 'POST':
        outcome_id = int(request.POST['winning_outcome_id'])
        outcome = get_object_or_404(Outcome, pk=outcome_id, market=mkt)
        settle_market(mkt, outcome)
        messages.success(request, 'Market settled.')
        return redirect('bets:market_detail', pk=mkt.pk)

    return render(request, 'bets/market_detail.html', {'market': mkt})


@login_required
def market_share_invite(request, pk: int):
    mkt = get_object_or_404(Market, pk=pk)
    if request.user != mkt.creator and request.user != mkt.house and not request.user.is_superuser:
        messages.error(request, "Only the market creator or house can share this market.")
        return redirect('bets:market_detail', pk=pk)

    if request.method == 'POST':
        form = MarketShareForm(request.POST)
        if form.is_valid():
            q = form.cleaned_data['query'].strip()
            u = User.objects.filter(username__iexact=q).first() or User.objects.filter(email__iexact=q).first()
            if not u:
                messages.error(request, "User not found.")
            elif MarketShare.objects.filter(market=mkt, user=u).exists():
                messages.info(request, f"Already shared with {u.username}.")
            elif MarketShareRequest.objects.filter(market=mkt, to_user=u, status=MarketShareRequest.PENDING).exists():
                messages.info(request, "Share request already pending.")
            else:
                MarketShareRequest.objects.create(market=mkt, from_user=request.user, to_user=u, seen=False)
                messages.success(request, f"Share request sent to {u.username}.")
            return redirect('bets:market_share_invite', pk=pk)
    else:
        form = MarketShareForm()

    shared_users = User.objects.filter(shared_markets__market=mkt).distinct()
    pending = MarketShareRequest.objects.filter(market=mkt, status=MarketShareRequest.PENDING)
    return render(request, 'bets/market_share.html', {'market': mkt, 'form': form, 'shared_users': shared_users, 'pending_requests': pending})


@login_required
@require_POST
def market_share_accept(request, req_id: int):
    rq = get_object_or_404(MarketShareRequest, pk=req_id, to_user=request.user, status=MarketShareRequest.PENDING)
    MarketShare.objects.get_or_create(market=rq.market, user=request.user, defaults={'added_by': rq.from_user})
    rq.status = MarketShareRequest.ACCEPTED; rq.save(update_fields=['status'])
    messages.success(request, f"Access granted to market: {rq.market.title}")
    return redirect('bets:dashboard')


@login_required
@require_POST
def market_share_decline(request, req_id: int):
    rq = get_object_or_404(MarketShareRequest, pk=req_id, to_user=request.user, status=MarketShareRequest.PENDING)
    rq.status = MarketShareRequest.DECLINED; rq.save(update_fields=['status'])
    messages.info(request, "Share request declined.")
    return redirect('bets:dashboard')


@login_required
@require_POST
def market_remove_user(request, pk: int, user_id: int):
    mkt = get_object_or_404(Market, pk=pk)
    if request.user != mkt.creator and request.user != mkt.house and not request.user.is_superuser:
        messages.error(request, "You don’t have permission to remove users from this market.")
        return redirect('bets:market_detail', pk=pk)

    target = get_object_or_404(User, pk=user_id)
    if target == mkt.creator or target == mkt.house:
        messages.error(request, "You can’t remove the creator/house from the market.")
        return redirect('bets:market_detail', pk=pk)

    active_bet_exists = Wager.objects.filter(user=target, market=mkt, market__status__in=[Market.OPEN, Market.SUSPENDED]).exists()
    if active_bet_exists:
        messages.error(request, "Cannot remove: user has an active bet in this market.")
        return redirect('bets:market_detail', pk=pk)

    MarketShare.objects.filter(market=mkt, user=target).delete()
    messages.success(request, f"Removed {target.username} from the market.")
    return redirect('bets:market_detail', pk=pk)


@login_required
def market_detail(request, pk: int):
    mkt = get_object_or_404(Market, pk=pk)

    wagers = mkt.wagers.select_related('user', 'outcome').all() if mkt.status == Market.SETTLED else []

    total_staked = sum((w.stake for w in wagers), Decimal('0.00'))

    total_payout_raw = sum((
        (w.stake * w.odds_at_placement) if w.outcome.is_winner else Decimal('0.00')
        for w in wagers
    ), Decimal('0.00'))

    total_payout = total_payout_raw.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    house_net    = (total_staked - total_payout).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    can_manage = (request.user == mkt.creator) or (request.user == mkt.house) or request.user.is_superuser

    ctx = {
        'market': mkt,
        'wagers': wagers,
        'total_staked': total_staked,
        'total_payout': total_payout,
        'house_net': house_net,
        'can_manage': can_manage,
    }
    return render(request, 'bets/market_detail.html', ctx)

@login_required
def market_history(request):
    f = request.GET.get('filter', 'all')

    created_qs = Market.objects.filter(creator=request.user, status=Market.SETTLED).prefetch_related('outcomes')
    bet_market_ids = (Wager.objects.filter(user=request.user, market__status=Market.SETTLED)
                      .values_list('market_id', flat=True).distinct())
    bet_qs = Market.objects.filter(id__in=bet_market_ids).prefetch_related('outcomes')

    if f == 'set_by_me':
        settled = created_qs.order_by('-created_at')
    elif f == 'bet_on':
        settled = bet_qs.order_by('-created_at')
    elif f == 'winning_bets':
        win_market_ids = (Wager.objects.filter(user=request.user, outcome__is_winner=True, market__status=Market.SETTLED)
                          .values_list('market_id', flat=True).distinct())
        settled = Market.objects.filter(id__in=win_market_ids).order_by('-created_at').prefetch_related('outcomes')
    elif f == 'winning_sets':
        all_my = created_qs
        settled = [m for m in all_my if _house_net_for(m) > 0]
    else:
        settled = (created_qs | bet_qs).order_by('-created_at').distinct()

    bettor_net = {}
    for mid in bet_market_ids:
        ws = Wager.objects.filter(user=request.user, market_id=mid).select_related('outcome')
        stakes = sum((w.stake for w in ws), Decimal('0.00'))
        pays = sum((
            (w.stake * w.odds_at_placement) if w.outcome.is_winner else Decimal('0.00')
            for w in ws
        ), Decimal('0.00'))
        bettor_net[mid] = (pays - stakes).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


    return render(request, 'bets/market_history.html', {
        'settled_markets': settled,
        'filter': f,
        'bettor_net': bettor_net,
    })


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You’ve been logged out.")
    return redirect('login')


@login_required
def friends(request):
    friends = User.objects.filter(friends_to__user=request.user).distinct()
    if request.method == 'POST':
        form = UserLookupForm(request.POST)
        if form.is_valid():
            q = form.cleaned_data['query'].strip()
            u = User.objects.filter(username__iexact=q).first() or User.objects.filter(email__iexact=q).first()
            if not u:
                messages.error(request, "User not found.")
            elif u == request.user:
                messages.error(request, "You can’t add yourself.")
            else:
                # create symmetric friendships if missing
                Friendship.objects.get_or_create(user=request.user, friend=u)
                Friendship.objects.get_or_create(user=u, friend=request.user)
                messages.success(request, f"Added {u.username} as a friend.")
            return redirect('bets:friends')
    else:
        form = UserLookupForm()
    return render(request, 'bets/friends.html', {'friends': friends, 'form': form})

def _house_net_for(mkt: Market) -> Decimal:
    ws = mkt.wagers.select_related('outcome').all()
    total_staked = sum((w.stake for w in ws), Decimal('0.00'))
    total_payout = sum(((w.stake * w.odds_at_placement) if w.outcome.is_winner else Decimal('0.00')) for w in ws)
    return (total_staked - total_payout)


@login_required
def friends(request):
    friends = User.objects.filter(friends_to__user=request.user).distinct()
    incoming = FriendshipRequest.objects.filter(to_user=request.user, status=FriendshipRequest.PENDING)
    outgoing = FriendshipRequest.objects.filter(from_user=request.user, status=FriendshipRequest.PENDING)

    if request.method == 'POST':
        form = UserLookupForm(request.POST)
        if form.is_valid():
            q = form.cleaned_data['query'].strip()
            u = User.objects.filter(username__iexact=q).first() or User.objects.filter(email__iexact=q).first()
            if not u:
                messages.error(request, "User not found.")
            elif u == request.user:
                messages.error(request, "You can’t friend yourself.")
            elif Friendship.objects.filter(user=request.user, friend=u).exists():
                messages.info(request, "Already friends.")
            elif FriendshipRequest.objects.filter(from_user=request.user, to_user=u, status=FriendshipRequest.PENDING).exists():
                messages.info(request, "Friend request already sent.")
            else:
                FriendshipRequest.objects.create(from_user=request.user, to_user=u, seen=False)
                messages.success(request, f"Friend request sent to {u.username}.")
            return redirect('bets:friends')
    else:
        form = UserLookupForm()

    return render(request, 'bets/friends.html', {
        'form': form,
        'friends': friends,
        'incoming': incoming,
        'outgoing': outgoing,
    })

@login_required
@require_POST
def friend_accept(request, req_id: int):
    fr = get_object_or_404(FriendshipRequest, pk=req_id, to_user=request.user, status=FriendshipRequest.PENDING)
    fr.status = FriendshipRequest.ACCEPTED; fr.save(update_fields=['status'])
    Friendship.objects.get_or_create(user=fr.from_user, friend=fr.to_user)
    Friendship.objects.get_or_create(user=fr.to_user, friend=fr.from_user)
    messages.success(request, f"You are now friends with {fr.from_user.username}.")
    return redirect('bets:friends')

@login_required
@require_POST
def friend_decline(request, req_id: int):
    fr = get_object_or_404(FriendshipRequest, pk=req_id, to_user=request.user, status=FriendshipRequest.PENDING)
    fr.status = FriendshipRequest.DECLINED; fr.save(update_fields=['status'])
    messages.info(request, "Friend request declined.")
    return redirect('bets:friends')

@login_required
@require_POST
def unfriend(request, user_id: int):
    other = get_object_or_404(User, pk=user_id)
    Friendship.objects.filter(user=request.user, friend=other).delete()
    Friendship.objects.filter(user=other, friend=request.user).delete()
    messages.success(request, f"Removed {other.username} from friends.")
    return redirect('bets:friends')


@login_required
def invites(request):
    event_incoming = EventInvite.objects.filter(to_user=request.user, status=EventInvite.PENDING).select_related('event','from_user')
    market_incoming = MarketShareRequest.objects.filter(to_user=request.user, status=MarketShareRequest.PENDING).select_related('market','from_user')
    friend_incoming = FriendshipRequest.objects.filter(to_user=request.user, status=FriendshipRequest.PENDING).select_related('from_user')

    friend_incoming.update(seen=True)
    event_incoming.update(seen=True)
    market_incoming.update(seen=True)

    return render(request, 'bets/invites.html', {
        'event_incoming': event_incoming,
        'market_incoming': market_incoming,
        'friend_incoming': friend_incoming,
    })
