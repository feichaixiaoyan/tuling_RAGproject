import os
from dotenv import load_dotenv
from mildoc_index.parser.parser_selector import Parser_Selector
from minio import Minio
from mildoc_index.logger.logger import setup_logging
from typing import Optional, Any
from minio.datatypes import EventIterable
from urllib.parse import unquote_plus
from mildoc_index.milvus_api import MilvusAPI, MilvusDocument
from mildoc_index.embedding import EmbeddingTool
import json
logger = setup_logging(__name__)
load_dotenv()  # 加载 .env 文件中的环境变量

MINIO_BUCKET = os.getenv("MINIO_BUCKET")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_REGION = os.getenv("MINIO_REGION")

MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "false").lower() == "true"
MINIO_USE_VIRTUAL_HOST = (
    os.getenv("MINIO_USE_VIRTUAL_HOST", "false").lower() == "true"
)

"""
这个文件是用来配置连接minio的客户端的 以及提供一些工具函数 比如从minio当中拿到文件的名字 以及把mime类型转换成简短的文件类型名称

"""

#配置连接minio的客户端
def get_minio_client() -> Minio:

    if not all([ MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY]):
        logger.error(
        "MinIO 配置不完整，请检查 .env 文件中的 MINIO_BUCKET、MINIO_ENDPOINT、MINIO_ACCESS_KEY 和 MINIO_SECRET_KEY 是否正确设置。"
    )
        raise ValueError(
        "MinIO 配置不完整，请检查 .env 文件中的 MINIO_BUCKET、MINIO_ENDPOINT、MINIO_ACCESS_KEY 和 MINIO_SECRET_KEY 是否正确设置。"
    )
    
    MINIO_CLIENT = Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL,
        # region=MINIO_REGION,
        # use_virtual_host=MINIO_USE_VIRTUAL_HOST,  # 如果使用虚拟主机模式，请取消注释
    )
    return MINIO_CLIENT




class MinioEventHandler:
    """
    用户上传文件 ----->minio保存文件---> minio产生事件----->监听器取出事件信息---->开始解析 切片----->milvus
    MinIO 有文件上传、删除事件
            ↓
    MinioEventHandler 接收事件
            ↓
    交给你的 Parser_Selector 解析
            ↓
    后面再交给向量化和 Milvus

    """
    #主要是用来处理minio的事件的 主要是文件上传和删除事件
    def __init__(self, bucket_name:str):
        self.bucket_name = bucket_name
        if not self.bucket_name:
            raise ValueError("MinIO 桶名称未配置，请检查 .env 文件中的 MINIO_BUCKET 是否正确设置。")
        
        self.minio_client = get_minio_client()
        self.parser_selector = Parser_Selector(self.minio_client)  # 初始化 Parser_Selector 实例
        logger.info(f"事件监听器 初始化完成，监听桶：{self.bucket_name}")
        self.embedding_tool = EmbeddingTool()  # 初始化 EmbeddingTool 实例
        self.milvus_api = MilvusAPI()  # 初始化 MilvusAPI 实例
        self.milvus_api.initialize()  # 确保 Milvus 集合已创建

    
                
    
    def extract_minio_event_info(self, event_data: dict[str, Any]) ->Optional[dict[str, Any]]:
        """

        从 MinIO 事件字典中提取关键信息。

        Args:
            event_dict (dict): MinIO 事件的字典表示。
            {   #每个records 代表一个事件 
                "Records": [
                    {
                        "eventName": "s3:ObjectCreated:Put",
                        "s3": {
                                    "s3SchemaVersion": "1.0",

                                    "configurationId": "Config",

                                    "bucket": {
                                        "name": "mildoc1",

                                        "ownerIdentity": {
                                            "principalId": "minioadmin"
                                        },

                                        "arn": "arn:aws:s3:::mildoc1"
                                    },

                                    "object": {
                                        "key": "documents%2Fgit%2FGit%E6%95%99%E7%A8%8B.pdf",
                                        "size": 1234567,
                                        "eTag": "4f9c12b64ae88d47d2d175c1a4c734a2",
                                        "contentType": "application/pdf",
                                        "userMetadata": {
                                            "content-type": "application/pdf"
                                        },
                                        "sequencer": "18DA13E56600A1BC"
                                    }
                        },

                    }
                ]
            }
            这个字典里面当中重要的字段是 
            event_name = "s3:ObjectCreated:Put"
            bucket_name = "mildoc1"
            object_name = "documents/git/git教程.pdf"
        Returns:
            Optional[dict]: 包含 'bucket_name'、'object_name' 和 'content_type' 的字典，
                            如果提取失败则返回 None。
        """
        event=event_data.get("Records", [])
        if not event:
            logger.error("MinIO 事件字典中没有 'Records' 键或其值为空。")
            return None
        event=event[0]  # 取第一个事件记录
        bucket_name=event.get("s3",{}).get("bucket",{}).get("name","")
        event_name =  unquote_plus(
                event.get("s3", {}).get("object", {}).get("key", "")
            )
        if not bucket_name or not event_name:
            logger.error("MinIO 事件字典中缺少 'bucket_name' 或 'object_name' 信息。")
            return None
        return {
            "event_name": event.get("eventName", ""),
            "event_time": event.get("eventTime", ""),
            "bucket_name": bucket_name,
            "object_name": event_name,
            "object_size": event.get("s3",{}).get("object",{}).get("size", 0),
            "content_type": event.get("s3",{}).get("object",{}).get("contentType", ""),
            "etag": event.get("s3",{}).get("object",{}).get("eTag", ""),
        }
    #处理事件 
    def process_event(self,event_info:dict[str,Any])->bool:
        """
        event_info  就是从事件字典当中 提取之后的信息 判断上传事件还是删除事件 
        """
        #判断是不是创建事件 因为创建事件 就是服务端上传了文件要进行parser 解析了 
        event_name=event_info["event_name"]
        bucket_name=event_info["bucket_name"] #??? 这里为什么不拿我自定义的那个bucket 这两个应该是同一个东西 
        object_name=event_info["object_name"] #这里应该是路径吧 叫object_name怪怪的 总是 
        if event_name.startswith("s3:ObjectCreated:"):
            """判断是不是创建事件 """
            return self.process_minio_object(bucket_name, object_name, force_update=True)

        if event_name.startswith("s3:ObjectRemoved:"):
            logger.info("收到删除事件：%s/%s", bucket_name, object_name)
            success = self.milvus_api.delete_existing_document(object_name)
            if success:
                logger.info("文档 %s 已从 Milvus 中删除。", object_name)
            else:
                logger.error("文档 %s 从 Milvus 中删除失败。", object_name)
        
            return success
        logger.warning("暂不支持的事件类型：%s", event_name)
        return False

    def text_to_vector_and_insert(self, document: dict[str, Any],force_update: bool = False) -> bool:
        """
        将文本块向量化并插入到 Milvus。

        Args:
            document (dict): 包含 'splited_texts' 的字典，表示分割后的文本块。
            force_update:有两种更新模式 
            为True的时候 直接删除掉 然后向量 存储
            False呢 还要再细分如果是存在了 那就跳过 如果不存在 则向量 存储
        """
        doc_path_name=document.get("doc_path_name", "")
        if not doc_path_name:
            logger.error("文档路径名称缺失，无法进行向量化和插入操作。")
            return False


        if not force_update:
            if self.milvus_api.check_document_exists(doc_path_name):
                logger.info("文档 %s 已存在于 Milvus，跳过插入操作。", doc_path_name)
                return True

        #强制更新模式 删除这个文档原本的
        if force_update:
            logger.info("强制更新文档 %s", doc_path_name)
            #删除掉在重新向量插入数据
            if not self.milvus_api.delete_existing_document(doc_path_name):
                logger.error("删除文档 %s 失败，无法进行向量化和插入操作。", doc_path_name)
                return False

        #第二种就是我要判断他是否存在 存在跳过 不存在删除    
        texts=document.get("splited_texts", [])
        if not texts:
                    logger.warning("文档中没有文本块，跳过向量化和插入操作。")
                    return False
        #1.文本向量化
        vectors=self.embedding_tool.get_embeddings(texts)
        if len(vectors) != len(texts):
            logger.error("文本块数量与向量数量不一致，停止写入")
            return False

        #2.准备插入到Milvus的文档列表
        documents_to_insert:list[MilvusDocument] = [MilvusDocument(
                
                    doc_name=document.get("doc_name", ""),
                    doc_type=document.get("doc_type", ""),
                    doc_md5=document.get("doc_md5", ""),
                    doc_length=document.get("doc_length", 0),
                    doc_path_name=document.get("doc_path_name", ""),
                    content=text,
                    content_vector=vector,
                    embedding_model=self.embedding_tool.model_name,
                )
                for text, vector in zip(texts, vectors)
        ]
        
        
        return self.milvus_api.insert_documents(documents_to_insert)
    def process_minio_object(self, bucket_name: str, object_name: str, force_update: bool = False) -> bool:
        """
            *下载 → 解析 → 切分 → 向量化 → 写入 Milvus 
        """
        try:
            logger.info("处理单个事件：%s/%s", bucket_name, object_name)
            #1.从minio当中下载 解析 切分文件
            document:dict[str, Any] | None=self.parser_selector.process_text_from_minio(bucket_name,object_name)
            if document is None:
                logger.warning("文档 %s/%s 解析失败，跳过向量化和插入操作。", bucket_name, object_name)
                return False
            #2.文本向量化并插入到Milvus
            success=self.text_to_vector_and_insert(document, force_update=force_update)
            if success:
                logger.info("文档 %s/%s 向量化并插入 Milvus 成功。", bucket_name, object_name)
            else:
                logger.error("文档 %s/%s 向量化或插入 Milvus 失败。", bucket_name, object_name)
            return success
        except Exception as e:
            logger.exception("处理文件失败")
            return False

    """
    全量更新
    """    
    def handle_minio_all_object(self):
        """
        处理 MinIO 桶中的所有事件。
        """
        logger.info("开始全量更新 MinIO 桶：%s", self.bucket_name)
        total=0
        success_count=0
        try:
            objects = self.minio_client.list_objects(self.bucket_name, recursive=True)
            for obj in objects:
                
                object_name=obj.object_name
                if not object_name or object_name.endswith("/"):
                    continue
                total+=1
                logger.info("当前处理%s个文件:%s",total,object_name)
                success=self.process_minio_object(bucket_name=self.bucket_name,object_name=object_name,force_update=True)
                if success:
                    success_count+=1
            #全部文件处理完之后 刷新一次
            self.milvus_api.flush_collection()
            logger.info(
            "全量更新完成，总文件数：%s,成功：%s,失败：%s",
                total,
                success_count,
                total - success_count,
            )

        except Exception as e:
            logger.exception("全量更新失败：%s", e)
    """
    排查补漏
    """
    def backfill_update(self) -> None:
        """
        检查 MinIO 中的所有文件，只补充 Milvus 中不存在的文件。
        这个很重要！！！！
        """
        logger.info("开始检查 MinIO 中缺失的文件：%s", self.bucket_name)

        total = 0
        existing_count = 0
        new_count = 0

        try:
            objects = self.minio_client.list_objects(
                bucket_name=self.bucket_name,
                recursive=True,
            )

            for obj in objects:
                object_name = obj.object_name
                # 跳过空名称和文件夹
                if not object_name or object_name.endswith("/"):
                    continue
                total += 1
                logger.info("正在检查第 %s 个文件：%s",total,object_name,)

                # Milvus 中已经存在就跳过
                if self.milvus_api.check_document_exists(object_name):
                    logger.info("文件已存在，跳过：%s", object_name)
                    existing_count += 1
                    continue

                # 不存在才解析、向量化并写入
                success = self.process_minio_object(
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    force_update=False,
                )

                if success:
                    new_count += 1

            self.milvus_api.flush_collection()

            logger.info(
                "补漏完成，总文件数：%s,已存在：%s,新增：%s,失败：%s",
                total,
                existing_count,
                new_count,
                total - existing_count - new_count,
            )

        except Exception as e:
            logger.exception("排查补漏失败：%s", e)

    """
    实时监听
    """        
    def start_listening_events(self):
        """
        持续监听当前桶的事件
        转换事件数据
        → 提取事件信息
        → 把事件交给 process_event() 
        """
        logger.info(f"开始监听桶 {self.bucket_name} 的事件...")
        try:
                """!!!!! 这个才是很关键的拿到的监听之后的事件信息 
                这里拿到原始的event 才会提取信息 拿到event_info 才会处理信息 """
                events:EventIterable = self.minio_client.listen_bucket_notification(
                        bucket_name=self.bucket_name,
                        prefix="",
                        suffix="",
                        events=["s3:ObjectCreated:*", "s3:ObjectRemoved:*"],#表示我要进听创建和删除事件操作
                    )
                for event in events:
                    if not event:
                        continue
                    #如果接收到了事件
                    #他客户端（minio_client） 返回的有可能是json 也有可能是字典
                    if  isinstance(event,dict):
                        event_data=event
                    else:
                        event_data=json.loads(event)
                    #从事件当中提取信息
                    event_info=self.extract_minio_event_info(event_data)
                    if event_info  is  None:
                        continue

                    logger.info("收到文件事件：%s",event_info)
                    #拿到事件处理信息了 接下来开始处理事件 
                    #这个document 包含了文档全部的信息 以及切片之后的文本块信息
                    
                    if not self.process_event(event_info):
                        logger.error("MinIO 事件处理失败：%s", event_info)        
        except KeyboardInterrupt:
            logger.error("已停止监听Minio")

    
if __name__ == '__main__':
   if __name__ == "__main__":
    handler = MinioEventHandler(bucket_name=MINIO_BUCKET)

    # 先确认配置的桶是否存在
    handler.start_listening_events()
        