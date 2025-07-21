from django.contrib import admin
from .models import Game

class GameAdmin(admin.ModelAdmin):
    list_filter = ('status',)
    list_display = ('when', 'status', 'description')
    date_hierarchy = 'when'
# Register your models here.
admin.site.register(Game, GameAdmin)