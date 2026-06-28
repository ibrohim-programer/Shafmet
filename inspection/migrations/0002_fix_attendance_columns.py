from django.db import migrations

def fix_attendance_columns(apps, schema_editor):
    from django.db import connection
    with connection.cursor() as cursor:
        # Check if table inspection_attendance exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inspection_attendance';")
        has_table = cursor.fetchone()
        
        if has_table:
            # Check existing columns
            cursor.execute("PRAGMA table_info(inspection_attendance);")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Rename user_id to worker_id if worker_id is missing and user_id exists
            if 'worker_id' not in columns and 'user_id' in columns:
                try:
                    cursor.execute("ALTER TABLE inspection_attendance RENAME COLUMN user_id TO worker_id;")
                except Exception:
                    pass
            
            # Add other missing columns
            missing_cols = [
                ("date", "DATE NOT NULL DEFAULT CURRENT_DATE"),
                ("check_in_time", "DATETIME NULL"),
                ("check_in_success", "BOOLEAN NOT NULL DEFAULT 0"),
                ("check_out_time", "DATETIME NULL"),
                ("check_out_success", "BOOLEAN NOT NULL DEFAULT 0"),
                ("is_late", "BOOLEAN NOT NULL DEFAULT 0")
            ]
            for col_name, col_type in missing_cols:
                # Refresh columns list
                cursor.execute("PRAGMA table_info(inspection_attendance);")
                current_cols = [row[1] for row in cursor.fetchall()]
                if col_name not in current_cols:
                    try:
                        cursor.execute(f"ALTER TABLE inspection_attendance ADD COLUMN {col_name} {col_type};")
                    except Exception:
                        pass
        else:
            # Table doesn't exist, which means it will be created by 0001_initial cleanly
            pass

def reverse_noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('inspection', '0001_initial'),
        ('account', '0002_seed_default_lavozimlar'),
    ]
    operations = [
        migrations.RunPython(fix_attendance_columns, reverse_noop),
    ]
