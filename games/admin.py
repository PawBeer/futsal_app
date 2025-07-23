from django.contrib import admin
from .models import Game, Player, PlayerStatus, BookingHistoryForGame

class GameAdmin(admin.ModelAdmin):
    list_filter = ('status',)
    list_display = ('when', 'status', 'description')
    date_hierarchy = 'when'
# Register your models here.
admin.site.register(Game, GameAdmin)
admin.site.register(Player)
admin.site.register(PlayerStatus)
admin.site.register(BookingHistoryForGame)