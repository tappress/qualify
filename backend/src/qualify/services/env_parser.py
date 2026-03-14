import re
from qualify.models.state import InfraInference

_POSTGRES = [r"DATABASE_URL", r"POSTGRES_", r"^PG_", r"DB_URL", r"DB_HOST", r"DB_NAME", r"DB_USER"]
_REDIS    = [r"REDIS_", r"CELERY_BROKER", r"CACHE_URL"]
_MINIO    = [r"S3_", r"AWS_S3", r"MINIO_", r"STORAGE_BUCKET"]


def parse_env_template(content: str) -> InfraInference:
    keys = [
        line.split("=", 1)[0].strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    ]
    inf = InfraInference()
    for key in keys:
        if any(re.search(p, key, re.IGNORECASE) for p in _POSTGRES):
            inf.postgres = True
        if any(re.search(p, key, re.IGNORECASE) for p in _REDIS):
            inf.redis = True
        if any(re.search(p, key, re.IGNORECASE) for p in _MINIO):
            inf.minio = True
    return inf
