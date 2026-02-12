import json
import logging
import math
from functools import lru_cache

import boto3

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _bedrock_runtime_client():
    return boto3.client("bedrock-runtime", region_name=settings.aws_region)


def embed_text_titan(text: str) -> list[float]:
    """
    Generate embedding with Amazon Titan Text Embeddings V2.
    """
    body = {"inputText": text or ""}
    try:
        client = _bedrock_runtime_client()
        resp = client.invoke_model(
            modelId=settings.titan_embed_model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        data = json.loads(resp["body"].read())
        emb = data.get("embedding")
        if isinstance(emb, list):
            return [float(x) for x in emb]
        # Defensive parsing for any alternate shape.
        if isinstance(data.get("embeddings"), list) and data["embeddings"]:
            first = data["embeddings"][0]
            if isinstance(first, list):
                return [float(x) for x in first]
        raise RuntimeError(f"Titan embedding response missing embedding vector: keys={list(data.keys())}")
    except Exception as e:
        logger.exception("Titan embedding call failed: %s", e)
        raise


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))
