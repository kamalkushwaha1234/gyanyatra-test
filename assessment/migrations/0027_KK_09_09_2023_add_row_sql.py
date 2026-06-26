from django.db import migrations

class Migration(migrations.Migration):
    """
    Migration Purpose:
    - This migration creates an `option_audit` table and a trigger (`option_audit_trigger`) to log all changes
      (INSERT, UPDATE, DELETE) made to the `assessment_option` table.
    - The `option_audit` table is used for auditing purposes, storing the following:
        - `option_id`: The UUID of the affected row in the `assessment_option` table.
        - `action`: The type of operation performed (`CREATE`, `UPDATE`, `DELETE`).
        - `old_value`: The state of the row before the change (for updates and deletes).
        - `new_value`: The state of the row after the change (for inserts and updates).
        - `changed_at`: The timestamp of the change.

    Why This is Needed:
    - To maintain a historical log of changes to the `assessment_option` table for auditing, debugging, and compliance purposes.
    - This ensures that all modifications to the `assessment_option` table are tracked automatically.

    How This File Was Generated:
    - This migration was created manually using the `migrations.RunSQL` operation to execute raw SQL commands.
    - The SQL commands include:
        1. Creating the `option_audit` table.
        2. Defining the `option_audit_trigger` function in PostgreSQL.
        3. Creating a trigger (`option_audit_trigger`) on the `assessment_option` table to log changes.

    Note:
    - The `option_audit` table does not have a corresponding Django model because it is used solely for logging purposes.
    - Queries to the `option_audit` table, if needed, must be written in raw SQL.
    """

    dependencies = [
        ('assessment', '0026_KK_09_09_2023_add_trigger'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS option_audit (
                    id SERIAL PRIMARY KEY,
                    option_id UUID NOT NULL,
                    action VARCHAR(10) NOT NULL,
                    old_value JSONB,
                    new_value JSONB,
                    changed_at TIMESTAMP DEFAULT NOW()
                );

                CREATE OR REPLACE FUNCTION option_audit_trigger()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF (TG_OP = 'INSERT') THEN
                        INSERT INTO option_audit(option_id, action, new_value)
                        VALUES (NEW.uuid, 'CREATE', row_to_json(NEW));
                        RETURN NEW;
                    ELSIF (TG_OP = 'UPDATE') THEN
                        INSERT INTO option_audit(option_id, action, old_value, new_value)
                        VALUES (NEW.uuid, 'UPDATE', row_to_json(OLD), row_to_json(NEW));
                        RETURN NEW;
                    ELSIF (TG_OP = 'DELETE') THEN
                        INSERT INTO option_audit(option_id, action, old_value)
                        VALUES (OLD.uuid, 'DELETE', row_to_json(OLD));
                        RETURN OLD;
                    END IF;
                END;
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS option_audit_trigger ON assessment_option;

                CREATE TRIGGER option_audit_trigger
                AFTER INSERT OR UPDATE OR DELETE ON assessment_option
                FOR EACH ROW
                EXECUTE FUNCTION option_audit_trigger();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS option_audit_trigger ON assessment_option;
                DROP FUNCTION IF EXISTS option_audit_trigger();
                DROP TABLE IF EXISTS option_audit;
            """
            )
        ]