from django import template

from games.helpers import player_helper
from games.models import StatusChoices

register = template.Library()


@register.filter
def get_display_name(player):
    # if your helper accepts a Player instance and returns a string:
    return player_helper.get_display_name(player)


@register.filter
def get_label_for_status(value: str) -> str:
    return StatusChoices(value).label
