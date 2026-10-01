"""Stable identifiers shared by indexing and query encoding."""
MODELS = {
    'minilm': {'name': 'MiniLM L6', 'model': 'sentence-transformers/all-MiniLM-L6-v2', 'dimensions': 384},
    'bge': {'name': 'BGE small EN v1.5', 'model': 'BAAI/bge-small-en-v1.5', 'dimensions': 384},
    'arctic': {'name': 'Snowflake Arctic S', 'model': 'snowflake/snowflake-arctic-embed-s', 'dimensions': 384},
}
ENCODING_VERSION = 'fastembed-0.8.1-chars600-overlap100-mean-v1'
