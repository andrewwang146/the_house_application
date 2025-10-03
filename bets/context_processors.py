from .models import FriendshipRequest, EventInvite, MarketShareRequest

def invite_counts(request):
    if not request.user.is_authenticated:
        return {'invite_count': 0}
    uid = request.user.id
    total = 0
    total += FriendshipRequest.objects.filter(to_user_id=uid, status='PENDING', seen=False).count()
    total += EventInvite.objects.filter(to_user_id=uid, status='PENDING', seen=False).count()
    total += MarketShareRequest.objects.filter(to_user_id=uid, status='PENDING', seen=False).count()
    return {'invite_count': total}
