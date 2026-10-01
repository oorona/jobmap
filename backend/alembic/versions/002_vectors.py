"""Current job corpus and versioned cosine-search vectors."""
from alembic import op
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    # A database administrator enables the extension before deployment.
    op.execute('''CREATE TABLE jev.search_jobs (
        id text PRIMARY KEY, content_version text NOT NULL, content_hash text NOT NULL,
        payload jsonb NOT NULL, description text NOT NULL, document text NOT NULL,
        expires_at timestamptz NOT NULL, updated_at timestamptz NOT NULL DEFAULT now())''')
    op.execute('CREATE INDEX search_jobs_expiry ON jev.search_jobs (expires_at)')
    op.execute('''CREATE TABLE jev.job_embeddings (
        job_id text REFERENCES jev.search_jobs(id) ON DELETE CASCADE,
        model text NOT NULL, content_hash text NOT NULL, encoding_version text NOT NULL,
        embedding public.vector(384) NOT NULL, indexed_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (job_id, model))''')
    # Exact cosine scans intentionally avoid ANN recall differences in this experiment.


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP TABLE jev.job_embeddings')
        op.execute('DROP TABLE jev.search_jobs')
