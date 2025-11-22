from django import template

from games.helpers import player_helper

register = template.Library()


@register.filter
def get_display_name(player):
    # if your helper accepts a Player instance and returns a string:
    return player_helper.get_display_name(player)
