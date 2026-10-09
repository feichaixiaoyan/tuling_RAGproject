import argparse
from mildoc_index.minio_event_handler import MinioEventHandler,MINIO_BUCKET
from mildoc_index.logger.logger import setup_logging


logger=setup_logging(__name__)

def main():
    #创建参数解析器
    parser=argparse.ArgumentParser(description="将 MinIO 中的文件解析并写入 Milvus")
    #告诉程序能接收哪些参数
    parser.add_argument(
        "--mode",required=True,choices=["full-refresh","backfill","listen"],
        help=(      "运行模式："
                    "full-refresh=全量更新，"
                    "backfill=排查补漏，"
                    "listen=实时监听"
                )
        
    )
    #读取和解析终端参数，得到 args 对象
    args=parser.parse_args()
    logger.info("索引服务启动，运行模式 %s",args.mode)
    handler=MinioEventHandler(bucket_name=MINIO_BUCKET)
    if args=="full-refresh":
        handler.handle_minio_all_object()
    elif args.mode == "backfill":
        handler.backfill_update()

    elif args.mode == "listen":
        handler.start_listening_events()

if __name__ == '__main__':
    main()