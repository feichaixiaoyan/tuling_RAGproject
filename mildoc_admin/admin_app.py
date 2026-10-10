import os
import uvicorn

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles #主要负责让浏览器访问 CSS、JavaScript、图片等静态资源。
from starlette.middleware.sessions import SessionMiddleware

from mildoc_admin.config.settings import ADMIN_HOST,ADMIN_PORT,BASE_DIR,PROJECT_ROOT,SESSION_SECRET_KEY
from mildoc_admin.routes.auth_routes import router as auth_router
from mildoc_admin.routes.file_routers import router as file_router

"""
    创建 FastAPI 应用
    → 配置 Session
    → 连接 MinIO 和 Milvus
    → 登录验证
    → 文件上传、浏览、下载和删除
    → 渲染管理页面

"""
app=FastAPI(title="mildoc管理后台端")

#增加 Session 功能，用来保存用户登录状态 通过中间件来实现的
"""
中间件干的事情读取 Cookie
→ 使用 SESSION_SECRET_KEY 重新计算签名
→ 比较签名
→ 签名正确
→ 解析 Session 内容
→ 放入 request.session
"""
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY

    )

#把处理静态数据的小应用 挂载到FASTapi应用上
#理解为给服务端的文件 配置一个对外访问入口 再给这个入口起一个内部名称
app.mount(
    "/resource",
    StaticFiles(directory=os.path.join(BASE_DIR,"static")), #它指定静态文件在电脑上保存的位置。
    name="static"
)

#把登录相关路由挂载到 FastAPI 应用上
app.include_router(auth_router)
app.include_router(file_router)


@app.get("/health")
async def health_check()->dict[str,str]:
    return {
        "status":"OK",
        "service":"mildoc"
    }


if __name__ == '__main__':
    print(BASE_DIR)
    print(PROJECT_ROOT)
    uvicorn.run(
        "mildoc_admin.admin_app:app",
        host=ADMIN_HOST,
        port=ADMIN_PORT,
        reload=True,
    )
