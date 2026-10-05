import os
from dotenv import load_dotenv
from mildoc_index.parser.parser_selector import Parser_Selector
from minio import Minio
from mildoc_index.logger.logger import setup_logging
from typing import Optional, Any
from minio.datatypes import EventIterable
from urllib.parse import unquote_plus
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
    def process_event(self,event_info:dict[str,Any])->dict[str, Any] | None:
        """
        event_info  就是从事件字典当中 提取之后的信息 
        """
        #判断是不是创建事件 因为创建事件 就是服务端上传了文件要进行parser 解析了 
        event_name=event_info["event_name"]
        bucket_name=event_info["bucket_name"] #??? 这里为什么不拿我自定义的那个bucket 这两个应该是同一个东西 
        object_name=event_info["object_name"] #这里应该是路径吧 叫object_name怪怪的 总是 
        if event_name.startswith("s3:ObjectCreated:"):
            """判断是不是创建事件 """
            spilted_doc:Optional[dict[str,Any]]=self.parser_selector.process_text_from_minio(bucket_name,object_name)
            return spilted_doc

        if event_name.startswith("s3:ObjectRemoved:"):
            logger.info("收到删除事件：%s/%s", bucket_name, object_name)
            return None

        return None
    #从minio接收事件 拿到这个event
    def start_listening_events(self):
        """
        持续监听当前桶的事件 
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
                    document=self.process_event(event_info)
                    if document is not None:
                        #打印日志
                        logger.info("文件解析完成，共得到%s个文本块",len(document["splited_texts"]))
        except KeyboardInterrupt:
            logger.error("已停止监听Minio")

    
if __name__ == '__main__':
    handler = MinioEventHandler(bucket_name=MINIO_BUCKET)
    sample_event = {
    "Records": [
        {
            "eventName": "s3:ObjectCreated:Put",
            "eventTime": "2026-09-30T10:00:00Z",
            "s3": {
                "bucket": {
                    "name": "mildoc1",
                },
                "object": {
                    "key": "测试文件/第一章.pdf",
                    "size": 1024,
                    "contentType": "application/pdf",
                    "eTag": "示例MD5",
                },
            },
        },
    ],
}

event_info = handler.extract_minio_event_info(sample_event)
print(event_info)
        