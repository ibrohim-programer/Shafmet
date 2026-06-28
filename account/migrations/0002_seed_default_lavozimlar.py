from django.db import migrations

def seed_default_lavozimlar(apps, schema_editor):
    connection = schema_editor.connection
    
    # Check if account_lavozim table exists
    if 'account_lavozim' not in connection.introspection.table_names():
        # Check if account_department exists
        if 'account_department' in connection.introspection.table_names():
            with connection.cursor() as cursor:
                # Rename table
                cursor.execute("ALTER TABLE account_department RENAME TO account_lavozim;")
                # Rename code to slug if exists
                try:
                    cursor.execute("ALTER TABLE account_lavozim RENAME COLUMN code TO slug;")
                except Exception:
                    pass
        else:
            # Create table account_lavozim
            is_postgres = connection.vendor == 'postgresql'
            pk_type = "BIGSERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
            created_at_type = "TIMESTAMP WITH TIME ZONE NOT NULL" if is_postgres else "DATETIME NOT NULL"
            
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS account_lavozim (
                        id {pk_type},
                        name VARCHAR(100) NOT NULL UNIQUE,
                        slug VARCHAR(50) NOT NULL UNIQUE,
                        description TEXT NULL,
                        show_in_diagram BOOLEAN NOT NULL DEFAULT FALSE,
                        is_default BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at {created_at_type}
                    );
                """)
                
    # Ensure new columns exist on account_lavozim
    if 'account_lavozim' in connection.introspection.table_names():
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(cursor, 'account_lavozim')
            existing_cols = [col.name for col in desc]
            
            is_postgres = connection.vendor == 'postgresql'
            datetime_type = "TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP" if is_postgres else "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            boolean_type = "BOOLEAN NOT NULL DEFAULT FALSE"
            
            columns_to_ensure = [
                ("description", "TEXT NULL"),
                ("show_in_diagram", boolean_type),
                ("is_default", boolean_type),
                ("created_at", datetime_type)
            ]
            for col_name, col_type in columns_to_ensure:
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE account_lavozim ADD COLUMN {col_name} {col_type};")
                    except Exception:
                        # Column already exists or another issue
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
