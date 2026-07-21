from django.contrib import admin

from .models import GamePrice, PlayerCharge, SettlementRun


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


admin.site.register(GamePrice)
admin.site.register(SettlementRun, SettlementRunAdmin)
admin.site.register(PlayerCharge, PlayerChargeAdmin)
