import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth.models import Group, User

from .models import ItineraryStop, Organization, TripEntry


def normalize_geo_location(value):
    value = value.strip()
    if not value:
        return ""

    coordinates = [coordinate.strip() for coordinate in value.split(",")]
    if len(coordinates) != 2:
        raise forms.ValidationError("Enter coordinates as latitude, longitude.")

    try:
        latitude, longitude = (Decimal(coordinate) for coordinate in coordinates)
    except InvalidOperation:
        raise forms.ValidationError("Enter valid numeric latitude and longitude.") from None

    if not latitude.is_finite() or not longitude.is_finite():
        raise forms.ValidationError("Latitude and longitude must be finite numbers.")
    if not Decimal("-90") <= latitude <= Decimal("90"):
        raise forms.ValidationError("Latitude must be between -90 and 90.")
    if not Decimal("-180") <= longitude <= Decimal("180"):
        raise forms.ValidationError("Longitude must be between -180 and 180.")

    return f"{latitude}, {longitude}"


class SignInForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class TripEntryForm(forms.ModelForm):
    geo_location = forms.CharField(
        required=False,
        max_length=64,
        label="Map coordinates",
        help_text="Enter latitude, longitude, for example 51.5072, -0.1276.",
        widget=forms.TextInput(attrs={"placeholder": "51.5072, -0.1276", "inputmode": "decimal"}),
    )

    class Meta:
        model = TripEntry
        fields = ["event_title", "event_date", "event_description", "geo_location"]
        widgets = {
            "event_title": forms.TextInput(),
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "event_description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_geo_location(self):
        return normalize_geo_location(self.cleaned_data["geo_location"])


class ItineraryStopForm(forms.ModelForm):
    geo_location = forms.CharField(
        required=False,
        max_length=64,
        label="Map coordinates",
        help_text="Enter latitude, longitude, for example 45.9932, -123.9226.",
        widget=forms.TextInput(attrs={"placeholder": "45.9932, -123.9226", "inputmode": "decimal"}),
    )

    class Meta:
        model = ItineraryStop
        fields = [
            "day_number", "stop_date", "destination", "preferred_campground", "alternate_campground",
            "check_in", "check_out", "route", "drive_time", "site_type", "booking_requirements",
            "price_or_membership", "booking_opening_estimate", "attractions", "landscape",
            "fuel_errands", "stop_category", "weather", "towing_notes", "booking_status",
            "booking_confirmation", "geo_location",
        ]
        widgets = {
            "stop_date": forms.DateInput(attrs={"type": "date"}),
            "check_in": forms.DateInput(attrs={"type": "date"}),
            "check_out": forms.DateInput(attrs={"type": "date"}),
            "booking_requirements": forms.Textarea(attrs={"rows": 2}),
            "attractions": forms.Textarea(attrs={"rows": 2}),
            "fuel_errands": forms.Textarea(attrs={"rows": 2}),
            "weather": forms.Textarea(attrs={"rows": 2}),
            "towing_notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_geo_location(self):
        return normalize_geo_location(self.cleaned_data["geo_location"])


class ItineraryCollisionForm(forms.ModelForm):
    class Meta:
        model = ItineraryStop
        fields = ["stop_date", "destination", "check_in", "check_out", "booking_status"]
        widgets = {
            "stop_date": forms.DateInput(attrs={"type": "date"}),
            "check_in": forms.DateInput(attrs={"type": "date"}),
            "check_out": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            for field in self.fields.values():
                field.widget.attrs["form"] = f"collision-form-{self.instance.pk}"


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
