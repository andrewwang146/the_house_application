from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')), # login/logout/password views
    path('', include('bets.urls')),
    path('', RedirectView.as_view(pattern_name='bets:dashboard', permanent=False)),
]