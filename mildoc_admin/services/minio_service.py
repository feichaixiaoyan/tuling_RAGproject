from minio import Minio
from datetime import timedelta, timezone
from mildoc_admin.config.settings import MINIO_ACCESS_KEY,MINIO_BUCKET,MINIO_ENDPOINT,MINIO_SECRET_KEY,MINIO_USE_SSL
from io import BytesIO #在内存当中 创建一个临时的二进制流对象
from minio.error import S3Error
import re
def create_minio_client()->Minio:
    return  Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL
    )

# 将 MinIO 返回的 UTC 时间转换成北京时间
def convert_utc_to_local(utc_datetime) -> str:
    """
    输入：MinIO 返回的 UTC 时间。
    输出：格式化后的北京时间字符串。
    作用：让管理页面显示我们习惯的北京时间。
    """
    if utc_datetime is None:
        return ""

    china_timezone = timezone(timedelta(hours=8))
    local_datetime = utc_datetime.astimezone(china_timezone)

    return local_datetime.strftime("%Y-%m-%d %H:%M:%S")

def get_minio_files(path:str="")->list[dict]:
    """
        输入path 要查看minio的目录
        输出 文件和文件夹
        作用:给admin端 也就是我后端 要拿到这些信息 要用的 提供文件列表
    """
    client=create_minio_client()
    if not client.bucket_exists(MINIO_BUCKET):
        raise ValueError("minio bucket 不存在")
    if path=="":
        search_prefix=""
    elif path.endswith("/"):
        search_prefix=path
    else:
        search_prefix=path+"/"
    objects=client.list_objects(
        bucket_name=MINIO_BUCKET,
        prefix=search_prefix,
        recursive=False
    )
    folders=[]
    files=[]
    folder_paths=set()#文件路径去重
    for object in objects:
        object_name=object.object_name
        if object_name == search_prefix:
            continue

        if object.is_dir:
            if object_name in folder_paths:
                continue
            folder_paths.add(object_name)
            folders.append({
                "name":object_name.rstrip("/").split("/")[-1],
                "path":object_name,
                "type":"folder",
                "size":0,
                "modified":""
            })
            continue
        files.append(
            {
                "name":object_name.split("/")[-1],
                "path":object_name,
                "type":"file",
                "size":object.size,
                "modified":convert_utc_to_local(object.last_modified)
            }
        )
    return folders + files


def upload_minio_file(file_name:str,data:bytes,path:str="",content_type="application/octet-stream")->dict:
    """
        输入：文件名称, 文件内容 ,上传到桶内的那个目录 默认是根目录 ,文件的MIME类型
        输出：上传成功返回文件名称 和对象路径 大小
                失败抛出异常
    """
    client=create_minio_client()
    if path:
        object_name=path.rstrip("/")+"/"+file_name
    else:
        object_name=file_name

    #查询同名文件 
    try:
        #获取对象信息
        client.stat_object(
            bucket_name=MINIO_BUCKET,
            object_name=object_name
        )
    #文件不存在的话 进入这里
    except S3Error as e:
        # 只有“对象不存在”才表示可以继续上传
        if e.code not in ("NoSuchKey", "NoSuchObject"):
            raise
    #查询成功 执行这里
    else:
        raise ValueError("文件已存在")
    #检查文件大小
    file_size=len(data)
    max_size=500 * 1024 * 1024
    if file_size >max_size:
        raise ValueError(f"文件过大{file_size}>{max_size}")

    #将数据包装成临时的二进制对象
    file_stream=BytesIO(data)
    client.put_object(
        bucket_name=MINIO_BUCKET,
        object_name=object_name,
        data=file_stream,
        length=file_size,
        content_type=content_type or "application/octet-stream"
    )
    #执行完之后 
    return {
        "filename":file_name,
        "size":file_size,
        "object_name":object_name
    }
    
def create_minio_directory(name:str,path:str="")->str:
    """
    name是创建的目录名称
    path是在哪里创建 默认采用根目录创建
    输出：成功返回创建的目录 失败抛出异常
    """
    name=name.strip()
    if not name:
         raise ValueError("目录名称不能为空")

    if re.search(r'[/\\:*?"<>|]', name):
        raise ValueError('目录名称不能包含以下字符：/ \\ : * ? " < > |')
    else:
        directory_path=name+"/" #minio当中的目录格式

    client=create_minio_client()
    try:
        #利用你不存在会 抛出异常来进行逻辑更新
        client.stat_object(
            bucket_name=MINIO_BUCKET,
            object_name=directory_path
        )
    #不存在报异常 停止
    except S3Error as e:
         if e.code not in ("NoSuchKey", "NoSuchObject"):
            raise #raise会让当前代码立即停止 并把错误交给调用他的代码处理
    #存在也报异常  并执行下面的操作
    else:
        raise ValueError("目录已经存在")
    #执行创建目录操作
    client.put_object(
        bucket_name=MINIO_BUCKET,
        object_name=directory_path,
        data=BytesIO(b""),
        length=0,
        content_type="application/x-directory"
    )
    return directory_path


    
if __name__ == '__main__':
    minio_files = get_minio_files()

    for minio_file in minio_files:
        print(minio_file)