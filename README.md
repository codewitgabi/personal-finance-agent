Personal Finance & Budgeting Agent

## Database Migrations

This project uses Alembic for database migrations. Follow these steps to manage database schema changes.

### Prerequisites

1. Ensure your `.env` file contains the `DATABASE_URL` environment variable
2. Make sure all model files are properly imported in `api/v1/models/__init__.py`

### Creating Migrations

1. **Auto-generate a migration** (recommended):

   ```bash
   alembic revision --autogenerate -m "Description of changes"
   ```

   This command will:

   - Compare your current models with the database schema
   - Generate a migration file with the necessary changes
   - Create the file in `alembic/versions/` directory

2. **Create an empty migration** (for manual changes):
   ```bash
   alembic revision -m "Description of changes"
   ```
   Then manually edit the generated migration file to add your changes.

### Reviewing Migrations

Before applying migrations, always review the generated migration file:

1. Open the migration file in `alembic/versions/`
2. Check the `upgrade()` function to ensure it contains the expected changes
3. Verify the `downgrade()` function can properly reverse the changes

### Applying Migrations

1. **Apply all pending migrations**:

   ```bash
   alembic upgrade head
   ```

   This will apply all migrations up to the latest version.

2. **Apply migrations up to a specific revision**:

   ```bash
   alembic upgrade <revision_id>
   ```

3. **Apply the next migration only**:
   ```bash
   alembic upgrade +1
   ```

### Rolling Back Migrations

1. **Rollback one migration**:

   ```bash
   alembic downgrade -1
   ```

2. **Rollback to a specific revision**:

   ```bash
   alembic downgrade <revision_id>
   ```

3. **Rollback all migrations**:
   ```bash
   alembic downgrade base
   ```

### Checking Migration Status

1. **View current database revision**:

   ```bash
   alembic current
   ```

2. **View migration history**:

   ```bash
   alembic history
   ```

3. **View detailed migration history**:
   ```bash
   alembic history --verbose
   ```

### Common Workflow

1. Make changes to your models in `api/v1/models/`
2. Generate a migration:
   ```bash
   alembic revision --autogenerate -m "Add new field to User model"
   ```
3. Review the generated migration file
4. Apply the migration:
   ```bash
   alembic upgrade head
   ```

### Troubleshooting

**Issue: Empty migration files (no changes detected)**

- Ensure all models are imported in `api/v1/models/__init__.py`
- Check that models inherit from `AbstractBaseModel` and have `__tablename__` defined
- Verify `alembic/env.py` imports all models with `from api.v1.models import *`

**Issue: Migration conflicts**

- Check current migration status: `alembic current`
- Review migration history: `alembic history`
- Resolve conflicts by editing migration files or creating merge migrations

**Issue: Database connection errors**

- Verify `DATABASE_URL` in `.env` file is correct
- Ensure the database server is running
- Check database credentials and permissions
