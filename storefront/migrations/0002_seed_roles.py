from django.db import migrations


ROLE_NAMES = ["ADMIN", "USER", "VIEWER", "EGGS"]


def create_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.using(schema_editor.connection.alias).bulk_create(
        [Group(name=name) for name in ROLE_NAMES],
        ignore_conflicts=True,
    )


def remove_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.using(schema_editor.connection.alias).filter(name__in=ROLE_NAMES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("storefront", "0001_initial"),
    ]

    operations = [migrations.RunPython(create_roles, remove_roles)]
