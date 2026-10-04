import re

from django import forms
from django.contrib.auth.models import Group, User

from .models import Organization, TripEntry


class SignInForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class TripEntryForm(forms.ModelForm):
    class Meta:
        model = TripEntry
        fields = ["event_title", "event_date", "event_description"]
        widgets = {
            "event_title": forms.TextInput(),
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "event_description": forms.Textarea(attrs={"rows": 4}),
        }


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "business_name",
            "street_address",
            "city",
            "state",
            "postal_code",
            "business_type",
            "business_start_date",
            "license",
            "registration_number",
        ]
        widgets = {
            "business_name": forms.TextInput(),
            "street_address": forms.TextInput(),
            "city": forms.TextInput(),
            "state": forms.TextInput(),
            "postal_code": forms.TextInput(),
            "business_type": forms.TextInput(),
            "business_start_date": forms.DateInput(attrs={"type": "date"}),
            "license": forms.TextInput(),
            "registration_number": forms.TextInput(),
        }


class RoleForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]

    def clean_name(self):
        name = self.cleaned_data["name"].strip().upper()
        if len(name) > 20 or not re.fullmatch(r"[A-Z][A-Z0-9_-]*", name):
            raise forms.ValidationError("Use up to 20 letters, numbers, underscores, or hyphens.")
        return name


class ManagedUserForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput)
    roles = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].queryset = Group.objects.order_by("name")
        if self.instance.pk and not self.is_bound:
            self.initial["roles"] = self.instance.groups.all()

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
            user.groups.set(self.cleaned_data["roles"])
        return user
