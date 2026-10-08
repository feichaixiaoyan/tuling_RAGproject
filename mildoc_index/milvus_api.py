from dataclasses import dataclass,asdict
from enum import Enum
from pymilvus import MilvusClient,DataType
import os
from typing import cast
from dotenv import load_dotenv
from mildoc_index.logger.logger import setup_logging
load_dotenv()


logger=setup_logging(__name__)
@dataclass


class MilvusDocument:
    """
        规定一条要存进 milvus的文档长什么样子
    """
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
        #获取配置
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
        #这个客户端 就是用来操作 milvus的客户端 以后的存储向量 创建集合 都有它来完成 
        self.client= MilvusClient(
                                  uri=f"http://{host}:{port}",
                                  user=user, 
                                  password=password,
                                  db_name=self.database_name
                                  
                                  )
        self.vector_dim = int(dimension) if dimension else None

    def create_collection_if_not_exists(self) -> bool:
        """
        创建集合
        """
        #判断集合是否存在
        if self.client.has_collection(self.collection_name):
            logger.info(f"集合 {self.collection_name} 已存在，跳过创建。")
            return True

        #不存在则创建集合 
        schema=self.client.create_schema(
            auto_id=True,
            #只按照我明确列出的字段存数据
            enable_dynamic_field=False,
        )
        #添加字段
        schema.add_field(
            field_name=MilvusDocumentField.ID.value,
            datatype=DataType.INT64,
            is_primary=True,
            auto_id=True,
        )
        schema.add_field(
            field_name=MilvusDocumentField.DOC_NAME.value,
            datatype=DataType.VARCHAR,
            max_length=500,
        )
        schema.add_field(
            field_name=MilvusDocumentField.DOC_PATH_NAME.value,
            datatype=DataType.VARCHAR,
            max_length=1000,
        )
        schema.add_field(
            field_name=MilvusDocumentField.DOC_TYPE.value,
            datatype=DataType.VARCHAR,
            max_length=50,
        )
        schema.add_field(
            field_name=MilvusDocumentField.DOC_MD5.value,
            datatype=DataType.VARCHAR,
            max_length=32,
        )
        schema.add_field(
            field_name=MilvusDocumentField.DOC_LENGTH.value,
            datatype=DataType.INT64,
        )
        schema.add_field(
            field_name=MilvusDocumentField.CONTENT.value,
            datatype=DataType.VARCHAR,
            max_length=65535,
        )
        schema.add_field(
            field_name=MilvusDocumentField.CONTENT_VECTOR.value,
            datatype=DataType.FLOAT_VECTOR,
            dim=self.vector_dim,
        )
        schema.add_field(
            field_name=MilvusDocumentField.EMBEDDING_MODEL.value,
            datatype=DataType.VARCHAR,
            max_length=100,
        )
        # 创建集合 这里的schema 是结构说明书 他会按照 什么样的结构 去创建 
        self.client.create_collection(collection_name=self.collection_name, schema=schema)
        logger.info(f"集合 {self.collection_name} 创建成功。")
        return True
    
    def create_index_if_not_exists(self) -> bool:
        """
        创建索引
        """
        #判断索引是否存在
        indexs=self.client.list_indexes(self.collection_name)
        if self.index_name in indexs:
            logger.info(f"索引 {self.index_name} 已存在，跳过创建。")
            return True
        #准备索引配置单 
        params=self.client.prepare_index_params()
        params.add_index(
            field_name=MilvusDocumentField.CONTENT_VECTOR.value,
            index_type="IVF_FLAT",
            index_name=self.index_name,
            metric_type="COSINE",
            params={"nlist": 1024},
        )

        self.client.create_index(
            collection_name=self.collection_name,
            index_params=params,
        )
        logger.info(f"索引 {self.index_name} 创建成功。")
        return True

    def load_collection(self) -> bool:
        """
        加载集合到milvus服务端的内存 把检索用的数据和索引准备到Milvus 服务端的内存中
        前面干的事情 是不把书存储到仓库 然后要查的书（数据）和目录（index）拿到阅览区 才能开始搜查
        """
        self.client.load_collection(self.collection_name,replica_number=1)
        logger.info(f"集合 {self.collection_name} 已加载到内存。")
        return True

    def initialize(self) -> None:
        """
        初始化 Milvus，创建集合、索引并加载集合到内存。
        """
        if not self.create_collection_if_not_exists():
            raise RuntimeError("创建集合失败。")

        if not self.create_index_if_not_exists():
            raise RuntimeError("创建索引失败。")

        if not self.load_collection():
            raise RuntimeError("加载集合到内存失败。")

        logger.info("Milvus 初始化完成。")

    def insert_documents(self, documents: list[MilvusDocument]) -> bool:
        """
        插入文档到 Milvus。

        Args:
            documents (list[MilvusDocument]): 要插入的文档列表。
        """
        if not documents:
            logger.warning("没有文档可插入，跳过操作。")
            return False

        try:
            #这里之所以要转换 是因为data的输入是一个字典列表 但是我们传入的是一个 dataclass的对象列表 所以要转换成字典列表
            data_to_insert: list[dict] = [asdict(doc) for doc in documents]
            result=self.client.insert(collection_name=self.collection_name, data=data_to_insert)
            count=result.get("insert_count", 0)
            logger.info(f"成功插入 {count} 条文档到集合 {self.collection_name}。")
            return count == len(documents)
        except Exception as e:
            logger.error(f"插入文档到milvus数据库失败: {e}")
            return False

    def check_document_exists(self, doc_path_name:str) -> bool:
        #检查 文档是否上传过 是这个函数的主要功能 
        """
            Milvus 中，搜索（Search）和查询（Query）是两种不同的数据检索方式。
            你可以先这样理解：

            - Search：找相似的数据。 例如，找出与用户问题语义最接近的 5 个文档片段。
            - Query：找满足条件的数据。 例如，找出 user_id = 1001 的所有文档片段。
        """

        #这里我们要检查文档是否存在 也就是要查询满足条件的数据 所以用query
        if doc_path_name is None or doc_path_name.strip() == "":
            raise ValueError("文档路径名不能为空。")

        result=self.client.query(
                collection_name=self.collection_name,
                 filter="doc_path_name == {path}",
                filter_params={"path": doc_path_name},
                #这个参数表示 我搜索返回的字段 只要id就行了 因为我们只是想知道这个文档是否存在 不需要其他字段
                output_fields=[MilvusDocumentField.ID.value]
            )
        return bool(result)  # 如果结果不为空，说明文档存在 

    def delete_existing_document(self, doc_path_name: str) -> bool:
        """
        删除已存在的文档的全部文本块。

        Args:
            doc_path_name (str): 要删除的文档路径名。
        """
        if doc_path_name is None or doc_path_name.strip() == "":
            raise ValueError("文档路径名不能为空。")

        try:
            # 删除满足条件的文档
            self.client.delete(
                collection_name=self.collection_name,
                filter="doc_path_name == {path}",
                filter_params={"path": doc_path_name}
            )
            logger.info(f"已删除文档: {doc_path_name}")
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False
    def flush_collection(self) -> bool:
        """
        将集合中的数据刷新到磁盘。 这里我不理解 
        """
        try:
            self.client.flush(self.collection_name)
            logger.info(f"集合 {self.collection_name} 刷新成功。")
            return True
        except Exception as e:
            logger.error(f"刷新集合失败: {e}")
            return False

    def search_similar_documents(self, query_vector: list[float], top_k: int =10) -> list[dict]:
        """
        搜索与查询向量最相似的文档。

        Args:
            query_vector (list[float]): 查询向量。
            top_k (int): 返回的最相似文档数量。
        Returns:
            相似文本块列表；搜索失败时返回空列表
        """
        try:
            #为什么会两层 嵌套list呢 因为 你输入一个问题 返回的是一个列表查找的结果 
            # 如果是多个问题 就是多个list返回的结果 
            #输出格式{"id":表当中的主键,"distance":向量相似度距离,"entity":{output_fields中指定的字段}}
            results:list[list[dict]] = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                search_params={"metric_type": "COSINE", "params": {"nprobe": 64}},
                limit=top_k,
                anns_field=MilvusDocumentField.CONTENT_VECTOR.value,
                output_fields=[
                    MilvusDocumentField.DOC_NAME.value,
                    MilvusDocumentField.DOC_PATH_NAME.value,
                    MilvusDocumentField.DOC_TYPE.value,
                    MilvusDocumentField.CONTENT.value,
                    MilvusDocumentField.EMBEDDING_MODEL.value
                ]
            )
            return results[0] if results else []
        except Exception as e:
            logger.error(f"搜索相似文档失败: {e}")
            return []

    def  get_collection_info(self) -> dict | None:
        """
        获取集合信息。
        """
        try:
            info = cast(dict,self.client.describe_collection(
                collection_name=self.collection_name
            ))
            return info

        except Exception as e:
            logger.error("获取集合信息失败: %s", e)
            return None
if __name__ == "__main__":
    api = MilvusAPI()
    collection_info = api.get_collection_info()

    if collection_info:
        print("集合信息：")
        print(collection_info)
    else:
        print("获取集合信息失败")