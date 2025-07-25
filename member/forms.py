from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from games.models import Player


class RegisterForm(UserCreationForm):
    nickname = forms.CharField(max_length=255, required=False)
    mobile_number = forms.CharField(
        max_length=9,
        required=True,
        help_text="Mobile number must contain exactly 9 digits",
    )
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'nickname', 'mobile_number')

    def clean_mobile_number(self):
        # you can copy the validator from your Player model here
        value = self.cleaned_data['mobile_number']
        import re
        if not re.match(r'^\d{9}$', value):
            raise forms.ValidationError("Mobile number must contain exactly 9 digits")
        return value