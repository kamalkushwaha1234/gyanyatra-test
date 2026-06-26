from django import forms
from .models import *
from django.contrib.auth.forms import UserCreationForm,AuthenticationForm,UsernameField


class SignUpForm(UserCreationForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={'placeholder':'Password','class':'validate form-control', 'aria-label': 'Password'}))
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput(attrs={'placeholder':'Confirm Password','class':'validate form-control', 'aria-label': 'Confirm Password'}))
    class Meta:
        model = User
        fields = ['email','first_name','last_name']
        labels = {'email':'Email','first_name':'First Name','last_name':'Last Name'}
        widgets = {k:forms.TextInput(attrs={'placeholder':v,'class':'validate form-control', 'aria-label': v}) for k,v in labels.items()}


class LoginForm(AuthenticationForm):
    username = UsernameField(widget=forms.TextInput(attrs={'autofocus':True,'placeholder':'Email','class':'validate form-control', 'aria-label': 'Email'}))
    password = forms.CharField(label="Password",strip=False,
            widget=forms.PasswordInput(attrs={'placeholder':'Password','class':'validate form-control', 'aria-label': 'Password'}))

class DownloadResultsForm(forms.Form):
    assessment = forms.ModelChoiceField(
        queryset=Assessment.objects.none(),
        empty_label="Select Assessment",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        required=False,
        empty_label="Select Organization",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    include_qna = forms.BooleanField(
        required=False,
        label="Include Questions and Answers",
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input", 
                "aria-label": "Include Individuals",
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        super(DownloadResultsForm, self).__init__(*args, **kwargs)
        assessments = Assessment.objects.filter(author=user)
        self.fields['assessment'].queryset = assessments

        organizations = Organization.objects.all()
        self.fields['organization'].queryset = organizations