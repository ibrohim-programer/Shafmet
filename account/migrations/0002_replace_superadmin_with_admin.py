from django.db import migrations, models


def replace_superadmin_with_admin(apps, schema_editor):
    User = apps.get_model("account", "UserModel")
    User.objects.filter(role="superadmin").update(role="admin")


def replace_admin_with_superadmin(apps, schema_editor):
    User = apps.get_model("account", "UserModel")
    User.objects.filter(role="admin").update(role="superadmin")


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            replace_superadmin_with_admin,
            replace_admin_with_superadmin,
        ),
        migrations.AlterField(
            model_name="usermodel",
            name="role",
            field=models.CharField(
                choices=[
                    ("boss", "Boss"),
                    ("admin", "Admin"),
                    ("manager", "Manager"),
                    ("worker", "Worker"),
                ],
                default="worker",
                max_length=20,
                verbose_name="Rol",
            ),
        ),
    ]
