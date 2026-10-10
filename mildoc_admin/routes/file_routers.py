from fastapi import APIRouter,Body
#fastapi的类型注解
from fastapi import Request,UploadFile,File,Form
from fastapi.responses import JSONResponse,RedirectResponse
import os
from mildoc_admin.routes.auth_routes import get_logged_in_username
from mildoc_admin.services.minio_service import get_minio_files,upload_minio_file,create_minio_directory
from fastapi.templating import Jinja2Templates
from mildoc_admin.config.settings import BASE_DIR
router=APIRouter()
templpates=Jinja2Templates(
    directory=os.path.join(BASE_DIR,"templates")
)

#获取minio的文件列表 
#FastAPI → 路由 → MinIO 服务 → 返回 JSON
@router.get("/api/files") #返回的文件数据   
async def get_files(request:Request,path:str=""):
    """
        输入：
        request：当前浏览器请求，用于检查登录状态。
        path：需要查看的 MinIO 目录，默认查看根目录。

        输出：
        登录成功时返回 MinIO 文件列表。
        未登录时返回 401。
        读取失败时返回 500。

        作用： 把 get_minio_files() 包装成浏览器可以访问的接口
    """
    user_name=get_logged_in_username(request=request)
    if user_name is None:
        return JSONResponse(
            status_code=401,
            content={"error":"用户未登录"}
        )

    try:
        files=get_minio_files(path=path)
        return {"files":files}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error":f"获取minio文件列表失败{e}"}
        )

@router.get("/files",name="file_browser")
async def file_browser(requset:Request,path:str=""):
    """
    输入：
        request：当前浏览器请求，用于检查登录状态。
        path：当前正在浏览的 MinIO 目录。

    输出：
        未登录时跳转到登录页面；
        已登录时返回 file_browser.html 页面。

    作用：
        提供管理后台的文件浏览页面入口。
    """
    user_name=get_logged_in_username(request=requset)
    #如果未登录 跳转到登陆界面
    if user_name is None:
        return RedirectResponse(
            url="/login",
            status_code=303
        )
    return templpates.TemplateResponse(
        request=requset,#请求示例
        name="file_browser.html",
        context={
            "current_path":path,
            "username":user_name
        }

    )

# 接收多个上传文件，逐个保存到 MinIO，并汇总上传结果
@router.post("/api/upload")
def api_upload_files(
    request:Request,
    files:list[UploadFile]=File(None),#从请求体中提取上传文件
    path:str=Form(""),#从请求体中提取表单字段
):
    """
    输出：
        成功文件列表、失败文件列表，以及各自的数量。

    作用：
        接收上传请求，调用上传服务，并返回前端需要的结果。
    """
    #判断用户是否登录
    username=get_logged_in_username(request=request)
    if username is None:
        return JSONResponse(
            status_code=401,
            content={"error":"用户未登录"}
        )

    if not files or all( not file.filename for file in files):
        return JSONResponse(
            status_code=400,
            content={"error":"所有文件名为空 或者 文件不存在"}
        )

    upload_files=[]
    failed_files=[]
    for file in files:
        if file.filename is None:
            continue

        try:
            #移动到文件的开头位置
                    file.file.seek(0)
                    #这才是读取的内容
            
                    data=file.file.read()
                    result:dict=upload_minio_file(
                        file_name=file.filename,
                        data=data,
                        path=path,
                        content_type=file.content_type
                    )
                    upload_files.append(result)
        except Exception as e:
             failed_files.append(
                  {"filename":file.filename,
                   "error":str(e)
                   }
             )
    message=f"成功上传了{len(upload_files)}个文件"
    if failed_files:
        message += f"{len(failed_files)} 个文件上传失败"

    return {
        "success": len(upload_files) > 0,
        "uploaded_count": len(upload_files),
        "failed_count": len(failed_files),
        "uploaded_files": upload_files,
        "failed_files": failed_files,
        "message": message,
    }
#接受创建目录的请求 
@router.post("/api/create-directory")
def api_create_directory(request:Request,data:dict[str,str]=Body(...)):
    """
    输入：
    request：当前请求，用于检查登录状态。
    data：JSON 数据，包含目录名称 name 和当前路径 path。

    输出：
    成功时返回 success 和 message。
    失败时返回 success 和 error。
    """
    username=get_logged_in_username(request=request)
    if username is None:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "用户未登录",
            },
        )
    try:
          create_minio_directory(name=data.get("name",""),path=data.get("path",""))
          return {
               "success":True,
               "message":"目录创建成功"
          }
    #名称为空、包含非法字符或者目录已经存在
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": str(e),
            },
        )
    except Exception as e:
         #minio连接的一些非人为因素错误
         return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"创建目录失败：{e}",
            },
        )