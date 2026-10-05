from dataclasses import dataclass
from enum import Enum
from pymilvus import MilvusClient
import os
from dotenv import load_dotenv
from mildoc_index.logger.logger import setup_logging
load_dotenv()
logger=setup_logging(__name__)
@dataclass
class MilvusDocument:
    doc_name: str
    doc_path_name: str
    doc_type: str
    doc_md5: str
    doc_length: int
    content: str
    content_vector: list[float]
    embedding_model: str
#字段对应清单
class MilvusDocumentField(str, Enum):
    ID = "id"
    DOC_NAME = "doc_name"
    DOC_PATH_NAME = "doc_path_name"
    DOC_TYPE = "doc_type"
    DOC_MD5 = "doc_md5"
    DOC_LENGTH = "doc_length"
    CONTENT = "content"
    CONTENT_VECTOR = "content_vector"
    EMBEDDING_MODEL = "embedding_model"

class MilvusAPI:
    def __init__(self):
        host = os.getenv("MILVUS_HOST")
        port = os.getenv("MILVUS_PORT")
        user = os.getenv("MILVUS_USER")
        password = os.getenv("MILVUS_PASSWORD")
        self.database_name = os.getenv("MILVUS_DATABASE")
        self.collection_name = os.getenv("MILVUS_COLLECTION")
        self.index_name = os.getenv("MILVUS_INDEX_NAME")
        dimension = os.getenv("MILVUS_VECTOR_DIM")

        if not all([host, port, user, password, self.database_name, self.collection_name, self.index_name, dimension]):
            raise ValueError("Milvus 配置不完整，请检查项目根目录的 .env")