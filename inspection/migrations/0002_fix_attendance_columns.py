from django.db import migrations

def fix_attendance_columns(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'inspection_attendance'
    
    if table_name in connection.introspection.table_names():
        with connection.cursor() as cursor:
            # Check existing columns
            desc = connection.introspection.get_table_description(cursor, table_name)
            columns = [col.name for col in desc]
            
            # Rename user_id to worker_id if worker_id is missing and user_id exists
            if 'worker_id' not in columns and 'user_id' in columns:
                try:
                    cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN user_id TO worker_id;")
                except Exception:
                    pass
            
            # Add other missing columns
            is_postgres = connection.vendor == 'postgresql'
            date_type = "DATE NOT NULL DEFAULT CURRENT_DATE"
            datetime_type = "TIMESTAMP WITH TIME ZONE NULL" if is_postgres else "DATETIME NULL"
            boolean_type = "BOOLEAN NOT NULL DEFAULT FALSE"
            
            missing_cols = [
                ("date", date_type),
                ("check_in_time", datetime_type),
                ("check_in_success", boolean_type),
                ("check_out_time", datetime_type),
                ("check_out_success", boolean_type),
                ("is_late", boolean_type)
            ]
            for col_name, col_type in missing_cols:
                # Refresh columns list
                desc = connection.introspection.get_table_description(cursor, table_name)
                current_cols = [col.name for col in desc]
                if col_name not in current_cols:
                    try:
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};")
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
