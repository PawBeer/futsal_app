from random import choices

from django import forms
from django.core.validators import RegexValidator, MinLengthValidator

from games.models import Player, Game


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = '__all__'

class GameForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-control  h-12 border-1'}),
        }