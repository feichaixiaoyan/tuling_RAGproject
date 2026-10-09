import os
import os.path
from dotenv import load_dotenv


# mildoc_admin 所在目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 项目根目录
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# mildoc_admin/.env 的准确路径
ADMIN_ENV_FILE = os.path.join(BASE_DIR, ".env")

# 明确加载管理后台自己的 .env
load_dotenv(ADMIN_ENV_FILE)

#后台管理相关的配置 
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8080"))

if not all([ADMIN_USERNAME,ADMIN_PASSWORD,SESSION_SECRET_KEY]):
    raise ValueError(" 管理后台配置不完整，请检查 ADMIN_USERNAME、"
        "ADMIN_PASSWORD 和 SESSION_SECRET_KEY")

#minio相关的配置
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET")
MINIO_USE_SSL = (
    os.getenv("MINIO_USE_SSL", "false").lower() == "true"
)

if not all([MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,]):
    raise ValueError("MinIO 配置不完整,请检查minio的相关配置")