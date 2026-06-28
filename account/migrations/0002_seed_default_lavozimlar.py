from django.db import migrations

def seed_default_lavozimlar(apps, schema_editor):
    Lavozim = apps.get_model('account', 'Lavozim')
    defaults = [
        ("Ichki do'kon ishchisi", 'ichki_dokon'),
        ("Tashqi do'kon ishchisi", 'tashqi_dokon'),
        ("Buxgalter", 'buxgalter'),
        ("Personal", 'personal'),
    ]
    for name, slug in defaults:
        Lavozim.objects.get_or_create(slug=slug, defaults={'name': name, 'is_default': True})

def reverse_noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('account', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed_default_lavozimlar, reverse_noop),
    ]
