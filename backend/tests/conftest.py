import os
import sys
import tempfile
from pathlib import Path
import pytest_asyncio
os.environ['SOURCE_MODE']='fixture'
os.environ['DATABASE_URL']='sqlite+aiosqlite:///'+str(Path(tempfile.mkdtemp(prefix='jev-test-'))/'ledger.db')
os.environ['REFINEMENT_ENABLED']='false'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import engine,Base

@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
