from random import choices

from django import forms
from django.core.validators import RegexValidator, MinLengthValidator

class PlayerForm(forms.Form):
    nickname = forms.CharField(
        max_length=255,
        label='Name',
        default='N/A',
        validators=[MinLengthValidator(3)],
        widget=forms.TextInput(attrs={'placeholder': 'Name'})
    )
    name = forms.CharField(
        max_length=255,
        label='Name',
        validators=[MinLengthValidator(3)],
        widget=forms.TextInput(attrs={'placeholder': 'Name'})
    )
    surname = forms.CharField(
        max_length=255,
        label='Surname',
        validators=[MinLengthValidator(3)],
        widget=forms.TextInput(attrs={'placeholder': 'Surname'})
    )
    email = forms.EmailField(
        max_length=255,
        label='Email',
        validators=[MinLengthValidator(3)],
        widget=forms.TextInput(attrs={'placeholder': 'Email'})
    )
    role = forms.CharField(
        max_length=10,
        label='Role',
        validators=[MinLengthValidator(3)],
        choices=[('Active','Active'),('Inactive','Inactive'),('Permanent','Permanent')]
    )
