from django.db import migrations

def seed_default_lavozimlar(apps, schema_editor):
    from django.db import connection
    with connection.cursor() as cursor:
        # Check if account_lavozim table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_lavozim';")
        has_lavozim = cursor.fetchone()
        
        if not has_lavozim:
            # Check if account_department exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_department';")
            has_department = cursor.fetchone()
            
            if has_department:
                # Rename table
                cursor.execute("ALTER TABLE account_department RENAME TO account_lavozim;")
                # Rename code to slug if exists
                try:
                    cursor.execute("ALTER TABLE account_lavozim RENAME COLUMN code TO slug;")
                except Exception:
                    pass
            else:
                # Create table account_lavozim
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS account_lavozim (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        slug VARCHAR(50) NOT NULL UNIQUE,
                        description TEXT NULL,
                        show_in_diagram BOOLEAN NOT NULL DEFAULT 0,
                        is_default BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL
                    );
                """)
                
        # Ensure new columns exist on account_lavozim
        columns = [
            ("description", "TEXT NULL"),
            ("show_in_diagram", "BOOLEAN NOT NULL DEFAULT 0"),
            ("is_default", "BOOLEAN NOT NULL DEFAULT 0"),
            ("created_at", "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ]
        for col_name, col_type in columns:
            try:
                cursor.execute(f"ALTER TABLE account_lavozim ADD COLUMN {col_name} {col_type};")
            except Exception:
                # Column already exists
                pass

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
