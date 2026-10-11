"""GCS-first artifact storage with a local development backend."""
import os
from pathlib import Path


def safe_segment(value: str) -> str:
    if not value or not all(c.isalnum() or c in "-_" for c in value):
        raise ValueError("Invalid storage identifier")
    return value


class Storage:
    def __init__(self, backend=None, bucket=None, prefix=None, local_dir=None):
        self.backend = backend or os.getenv("STORAGE_BACKEND", "gcs")
        self.prefix = (prefix if prefix is not None else os.getenv("GCS_PREFIX", "mindmapping_study")).strip("/")
        if any(p in (".", "..") for p in self.prefix.split("/")):
            raise ValueError("Invalid GCS prefix")
        if self.backend == "gcs":
            from google.cloud import storage
            name = bucket or os.getenv("GCS_BUCKET")
            if not name:
                raise ValueError("Set GCS_BUCKET to an existing Google Cloud Storage bucket")
            self.bucket = storage.Client().bucket(name)
        elif self.backend == "local":
            self.root = Path(local_dir or os.getenv("LOCAL_DATA_DIR", "./local_data")).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
        else:
            raise ValueError("STORAGE_BACKEND must be gcs or local")

    def _key(self, key):
        parts = key.split("/")
        if not parts or any(not p or p in (".", "..") for p in parts):
            raise ValueError("Invalid object key")
        return "/".join(safe_segment(p.rsplit(".", 1)[0]) + ("." + p.rsplit(".", 1)[1] if "." in p else "") for p in parts)

    def _full_key(self, key):
        key = self._key(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def put(self, key, data: bytes, content_type="application/octet-stream"):
        key = self._full_key(key)
        if self.backend == "gcs":
            self.bucket.blob(key).upload_from_string(data, content_type=content_type)
        else:
            path = self.root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)

    def get(self, key):
        key = self._full_key(key)
        if self.backend == "gcs":
            blob = self.bucket.blob(key)
            if not blob.exists():
                return None
            return blob.download_as_bytes()
        path = self.root / key
        return path.read_bytes() if path.is_file() else None

    def list(self, prefix=""):
        full = f"{self.prefix}/{prefix}" if self.prefix else prefix
        if self.backend == "gcs":
            return [b.name[len(self.prefix) + 1:] if self.prefix else b.name for b in self.bucket.list_blobs(prefix=full)]
        root = self.root / self.prefix
        if not root.exists():
            return []
        return [str(p.relative_to(root)).replace(os.sep, "/") for p in root.rglob("*") if p.is_file() and str(p.relative_to(root)).replace(os.sep, "/").startswith(prefix)]
