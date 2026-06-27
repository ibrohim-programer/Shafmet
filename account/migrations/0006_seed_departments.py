from django.db import migrations

def seed_departments(apps, schema_editor):
    Department = apps.get_model('account', 'Department')
    
    departments = [
        {"name": "Ichki do'kon ishchisi", "code": "ichki_dokon"},
        {"name": "Tashqi do'kon ishchisi", "code": "tashqi_dokon"},
        {"name": "Buxgalter", "code": "buxgalter"},
        {"name": "Personal (Kadrlar)", "code": "personal"},
    ]
    
    for dept in departments:
        Department.objects.get_or_create(code=dept["code"], defaults={"name": dept["name"]})

def reverse_seed_departments(apps, schema_editor):
    Department = apps.get_model('account', 'Department')
    Department.objects.filter(code__in=["ichki_dokon", "tashqi_dokon", "buxgalter", "personal"]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('account', '0005_department_usermodel_department'),
    ]

    operations = [
        migrations.RunPython(seed_departments, reverse_seed_departments),
    ]
