import os
import tempfile

from minio import Minio

from app.core.config import settings

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def download_artifact(artifact_prefix: str) -> str:
    """Download all objects under a MinIO prefix into a temp directory."""
    storage = get_minio_client()
    tmp_dir = tempfile.mkdtemp(prefix="llmflow_serve_")
    objects = storage.list_objects(settings.minio_bucket, prefix=artifact_prefix, recursive=True)
    found = False
    for obj in objects:
        found = True
        rel_path = obj.object_name[len(artifact_prefix) :].lstrip("/")
        if not rel_path:
            continue
        local_path = os.path.join(tmp_dir, rel_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        storage.fget_object(settings.minio_bucket, obj.object_name, local_path)
    if not found:
        raise FileNotFoundError(f"No artifacts at prefix {artifact_prefix}")
    return tmp_dir
