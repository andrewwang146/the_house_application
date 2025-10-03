from django.urls import path
from . import views


app_name = 'bets'


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('deposit/', views.deposit_view, name='deposit'),

    path('friends/', views.friends, name='friends'),
    path('friends/accept/<int:req_id>/', views.friend_accept, name='friend_accept'),
    path('friends/decline/<int:req_id>/', views.friend_decline, name='friend_decline'),
    path('friends/remove/<int:user_id>/', views.unfriend, name='unfriend'),

    path('events/new/', views.event_create, name='event_create'),
    path('events/<int:pk>/', views.event_detail, name='event_detail'),
    path('events/<int:pk>/invite/', views.event_invite, name='event_invite'),
    path('events/invite/<int:invite_id>/accept/', views.event_invite_accept, name='event_invite_accept'),
    path('events/invite/<int:invite_id>/decline/', views.event_invite_decline, name='event_invite_decline'),
    path('events/<int:pk>/remove/<int:user_id>/', views.event_remove_member, name='event_remove_member'),


    path('markets/new/', views.market_create, name='market_create'),
    path('markets/<int:pk>/', views.market_detail, name='market_detail'),
    path('markets/<int:pk>/share/', views.market_share_invite, name='market_share_invite'),
    path('markets/<int:pk>/settle/', views.market_settle, name='market_settle'),
    
    path('markets/share/<int:req_id>/accept/', views.market_share_accept, name='market_share_accept'),
    path('markets/share/<int:req_id>/decline/', views.market_share_decline, name='market_share_decline'),
    path('markets/<int:pk>/remove/<int:user_id>/', views.market_remove_user, name='market_remove_user'),

    path('markets/<int:pk>/settle/', views.market_settle, name='market_settle'),
    path('markets/history/', views.market_history, name='market_history'),

    path('invites/', views.invites, name='invites'),

    path('logout/', views.logout_view, name='logout'),
]