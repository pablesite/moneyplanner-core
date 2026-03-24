from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        (
            "memberships",
            "0004_rename_memberships_user_id_247f36_idx_memberships_user_id_bd713b_idx_and_more",
        ),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE c.conname = 'uniq_member_name_per_user'
                      AND t.relname = 'memberships_familymember'
                ) THEN
                    ALTER TABLE memberships_familymember
                    RENAME CONSTRAINT uniq_member_name_per_user
                    TO uniq_member_name_per_user_memberships;
                END IF;
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE c.conname = 'ownership_individual_requires_member'
                      AND t.relname = 'memberships_ownership'
                ) THEN
                    ALTER TABLE memberships_ownership
                    RENAME CONSTRAINT ownership_individual_requires_member
                    TO ownership_individual_requires_member_memberships;
                END IF;
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE c.conname = 'uniq_split_member_per_ownership'
                      AND t.relname = 'memberships_ownershipsplit'
                ) THEN
                    ALTER TABLE memberships_ownershipsplit
                    RENAME CONSTRAINT uniq_split_member_per_ownership
                    TO uniq_split_member_per_ownership_memberships;
                END IF;
            END
            $$;
            """,
            reverse_sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE c.conname = 'uniq_member_name_per_user_memberships'
                      AND t.relname = 'memberships_familymember'
                ) THEN
                    ALTER TABLE memberships_familymember
                    RENAME CONSTRAINT uniq_member_name_per_user_memberships
                    TO uniq_member_name_per_user;
                END IF;
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE c.conname = 'ownership_individual_requires_member_memberships'
                      AND t.relname = 'memberships_ownership'
                ) THEN
                    ALTER TABLE memberships_ownership
                    RENAME CONSTRAINT ownership_individual_requires_member_memberships
                    TO ownership_individual_requires_member;
                END IF;
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE c.conname = 'uniq_split_member_per_ownership_memberships'
                      AND t.relname = 'memberships_ownershipsplit'
                ) THEN
                    ALTER TABLE memberships_ownershipsplit
                    RENAME CONSTRAINT uniq_split_member_per_ownership_memberships
                    TO uniq_split_member_per_ownership;
                END IF;
            END
            $$;
            """,
        )
    ]
