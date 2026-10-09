from minio import Minio

from mildoc_admin.config.settings import MINIO_ACCESS_KEY,MINIO_BUCKET,MINIO_ENDPOINT,MINIO_SECRET_KEY,MINIO_USE_SSL

def create_minio_client()->Minio:
    return  Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL
    )

if __name__ == '__main__':
    client=create_minio_client()
    exists=client.bucket_exists(MINIO_BUCKET)
    print("Minio桶名称",MINIO_BUCKET)
    print("是否存在:",exists)