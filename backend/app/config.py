import os
from pathlib import Path
from sqlalchemy import URL


def secret(name: str) -> str:
    path = Path('/run/secrets') / name
    return path.read_text().strip() if path.exists() else os.getenv(name.upper(), '')


HOST = os.getenv('PROJECT_HOST', 'localhost')
SOURCE_MODE = os.getenv('SOURCE_MODE', 'live')
UPSTREAM = os.getenv('MEXICODEV_API_URL', 'https://mexicodev.org/api/jobs/v1').rstrip('/')
MODEL = 'jev-1.13.0'
RUBRIC = 'relevance-4'
DB_URL = os.getenv('DATABASE_URL') or URL.create('postgresql+asyncpg', username='jev', password=secret('db_password'), host=os.getenv('POSTGRES_HOST', 'postgres'), database='jev')
REFINEMENT_ENABLED = os.getenv('REFINEMENT_ENABLED', 'false').lower() == 'true'
