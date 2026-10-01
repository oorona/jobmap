"""Internal CPU encoder. Document and query encoding use model-specific prefixes."""
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Literal
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastembed import TextEmbedding
from embedding_models import MODELS, ENCODING_VERSION

models = {}
locks = {key: asyncio.Lock() for key in MODELS}
load_error = None


def load():
    global load_error
    try:
        for key, spec in MODELS.items():
            models[key] = TextEmbedding(model_name=spec['model'], cache_dir='/models', threads=1)
    except Exception as exc:
        load_error = type(exc).__name__
        raise


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(load)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


class Encode(BaseModel):
    model: Literal['minilm', 'bge', 'arctic']
    kind: Literal['query', 'document']
    texts: list[str] = Field(min_length=1, max_length=16)


def chunks(text):
    # Cover the whole posting instead of silently embedding only its opening.
    return [text[start:start+600] for start in range(0, max(1, len(text)), 500)]


def encode(body):
    model = models[body.model]
    if body.kind == 'query':
        return [v.tolist() for v in model.query_embed(body.texts)]
    output = []
    for text in body.texts:
        vectors = np.asarray(list(model.passage_embed(chunks(text), batch_size=16)))
        mean = vectors.mean(axis=0)
        norm = np.linalg.norm(mean)
        if not np.isfinite(norm) or norm == 0:
            raise ValueError('Invalid embedding')
        output.append((mean/norm).tolist())
    return output


@app.get('/health')
def health():
    if len(models) != len(MODELS):
        raise HTTPException(503, 'Models loading')
    return {'status': 'ok', 'models': MODELS, 'encoding_version': ENCODING_VERSION}


@app.post('/embed')
async def embed(body: Encode):
    if any(not text.strip() or len(text)>52000 for text in body.texts):
        raise HTTPException(422, 'Text must contain 1 to 52000 characters')
    if body.kind == 'query' and any(len(text)>500 for text in body.texts):
        raise HTTPException(422, 'Query too long')
    started = time.perf_counter()
    async with locks[body.model]:
        vectors = await asyncio.to_thread(encode, body)
    return {'vectors': vectors, 'elapsed_ms': (time.perf_counter()-started)*1000,
            'model': MODELS[body.model]['model'], 'encoding_version': ENCODING_VERSION}
