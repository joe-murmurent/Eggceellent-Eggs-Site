from django.db import migrations, models


def normalize_status(apps, schema_editor):
    ItineraryStop = apps.get_model("storefront", "ItineraryStop")
    for stop in ItineraryStop.objects.all():
        status = "Booked" if stop.booking_status.strip().lower() in ("booked", "final") else "Book"
        if stop.booking_status != status:
            stop.booking_status = status
            stop.save(update_fields=["booking_status"])


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0006_itinerarystop_booking_confirmation"),
    ]

    operations = [
        migrations.RunPython(normalize_status, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="itinerarystop",
            name="booking_status",
            field=models.CharField(
                choices=[("Book", "Book"), ("Booked", "Booked")], default="Book", max_length=40
            ),
        ),
    ]
