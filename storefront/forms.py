from django import forms


class EnquiryForm(forms.Form):
    name = forms.CharField(max_length=100, label="Your name")
    email = forms.EmailField(label="Email address")
    quantity = forms.ChoiceField(
        choices=[
            ("6 eggs", "A half-dozen"),
            ("12 eggs", "A dozen"),
            ("30 eggs", "A baker's box (30)")
        ],
        label="What are you after?",
    )
    message = forms.CharField(
        max_length=1200,
        label="Anything else?",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
