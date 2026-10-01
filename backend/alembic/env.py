import asyncio
from alembic import context
from app.db import Base, engine

def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, version_table_schema='jev', include_schemas=True)
    with context.begin_transaction():
        context.run_migrations()

async def main():
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()

asyncio.run(main())
