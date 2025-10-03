from django.contrib import admin
from .models import Wallet, Transaction, Event, Market, Outcome, Wager, EventWallet, EventTransaction, UserSettings

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user','balance')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user','type','amount','created_at','note')
    list_filter = ('type',)

class OutcomeInline(admin.TabularInline):
    model = Outcome
    extra = 0

@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('title','event','creator','house','house_margin','max_bet_limit','status','created_at')
    inlines = [OutcomeInline]

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user','default_max_bet_limit')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name','creator','default_house','is_active','created_at')

@admin.register(Wager)
class WagerAdmin(admin.ModelAdmin):
    list_display = ('user','market','outcome','stake','odds_at_placement','status','placed_at')

@admin.register(EventWallet)
class EventWalletAdmin(admin.ModelAdmin):
    list_display = ('event','balance')

@admin.register(EventTransaction)
class EventTransactionAdmin(admin.ModelAdmin):
    list_display = ('event','type','amount','created_at','note')
    list_filter  = ('type',)
