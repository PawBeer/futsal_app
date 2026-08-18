from django.contrib import admin

from .models import (
    BookingHistoryForGame,
    ChatMessage,
    Game,
    GamePrice,
    Player,
    PlayerCharge,
    SettlementRun,
)


class GameAdmin(admin.ModelAdmin):
    list_filter = ("status",)
    list_display = ("when", "status", "description")
    date_hierarchy = "when"


class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "created_at")
    list_filter = ("user",)
    date_hierarchy = "created_at"


class SettlementRunAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "send_count", "last_sent_at", "created_at")
    list_filter = ("year", "month")


class PlayerChargeAdmin(admin.ModelAdmin):
    list_display = (
        "settlement_run",
        "player",
        "amount",
        "game_count",
        "is_paid",
        "paid_at",
        "marked_by",
    )
    list_filter = ("is_paid", "settlement_run")


# Register your models here.
admin.site.register(Game, GameAdmin)
admin.site.register(BookingHistoryForGame)
admin.site.register(ChatMessage, ChatMessageAdmin)
admin.site.register(Player)
admin.site.register(GamePrice)
admin.site.register(SettlementRun, SettlementRunAdmin)
admin.site.register(PlayerCharge, PlayerChargeAdmin)
