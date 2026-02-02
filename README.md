# moneyplanner


## Database backup & restore (local dev)

This project includes safe scripts to dump and restore the local PostgreSQL database
(using Docker). They are designed to work on Windows with Git Bash.

### Create a database backup

Creates a binary dump (`.dump`) in `backups/` and verifies it automatically.

```bash
"C:\Program Files\Git\usr\bin\bash.exe" scripts/db_dump.sh
```

### Restore the latest backup

Finds the most recent dump in backups/, asks for confirmation, and restores it safely.
A safety backup is created automatically before restoring.

```bash
"C:\Program Files\Git\usr\bin\bash.exe" scripts/db_restore_latest.sh
```

You must type YES to confirm the restore.

Notes

- Dumps are verified using pg_restore -l before any destructive operation.
- Restores will abort if the dump is invalid.
- A pre_restore_*.dump safety backup is always created before restoring.
- Never use -t with pg_dump -Fc (binary dumps).