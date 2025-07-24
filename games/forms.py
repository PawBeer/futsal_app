from random import choices

from django import forms
from django.core.validators import RegexValidator, MinLengthValidator

from games.models import Player


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = '__all__'
