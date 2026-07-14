from django.contrib import admin

from .models import BookingHistoryForGame, ChatMessage, Game


class GameAdmin(admin.ModelAdmin):
    list_filter = ("status",)
    list_display = ("when", "status", "description")
    date_hierarchy = "when"


class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "created_at")
    list_filter = ("user",)
    date_hierarchy = "created_at"


# Register your models here.
admin.site.register(Game, GameAdmin)
admin.site.register(BookingHistoryForGame)
admin.site.register(ChatMessage, ChatMessageAdmin)
