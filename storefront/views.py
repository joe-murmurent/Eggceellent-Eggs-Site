from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render

from .forms import EnquiryForm


def home(request):
    form = EnquiryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        subject = f"Egg enquiry from {data['name']}"
        body = (
            f"Name: {data['name']}\n"
            f"Email: {data['email']}\n"
            f"Looking for: {data['quantity']}\n\n"
            f"{data['message']}"
        )
        EmailMessage(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [settings.CONTACT_EMAIL],
            reply_to=[data["email"]],
        ).send()
        messages.success(request, "Thanks for getting in touch. We'll be back to you soon.")
        return redirect("home")

    return render(request, "storefront/home.html", {"form": form})
