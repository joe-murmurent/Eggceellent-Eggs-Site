from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0005_itineraryreference_itinerarystop"),
    ]

    operations = [
        migrations.AddField(
            model_name="itinerarystop",
            name="booking_confirmation",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]