import os
from fastapi import APIRouter,Request,Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates #将python数据 渲染到html的模板当中

from mildoc_admin.config.settings import ADMIN_PASSWORD,ADMIN_USERNAME,BASE_DIR

"""
登录退出 相关路由 
"""
router=APIRouter()

#创建模板引擎
templates=Jinja2Templates(directory=os.path.join(BASE_DIR,"templates"))


def get_logged_in_username(request:Request)->str|None:
    #获取已经登陆的用户名
    return request.session.get("username")


#登录路由
@router.get("/")
async def home(request:Request):
    """
    管理后台页面 未登录跳转到登录页面 已登录返回用户信息
    """
    user_name=get_logged_in_username(request=request)
    if user_name is None:
        return RedirectResponse(
            url="/login",
            status_code=303
        )
    return {
        "message":"登陆成功",
        "username":user_name
    }


@router.get("/login")
async def login_page(request:Request):
    """显示登录页面"""
    user_name=get_logged_in_username(request=request)
    #已经登陆了 跳转到首页
    if user_name is not None:
        return RedirectResponse(
            "/",
            status_code=303
        )
    #没有登陆返回 登陆页面
    return templates.TemplateResponse(
        request=request,#把当前请求对象 交给
        name="login.html",#本次要使用的模板文件
        context={
                "error":None
        }
    )


@router.post("/login")
async def login(request:Request,username:str=Form(...),password:str=Form(...)):
    """
    真正执行登录
    验证登录账号和密码。

    输入：
        username：登录表单中的用户名。
        password：登录表单中的密码。

    输出：
        成功时跳转首页；
        失败时重新显示登录页面。
    """
    if (username==ADMIN_USERNAME and password==ADMIN_PASSWORD):
        request.session["username"]=username
        return RedirectResponse(
            "/",
            status_code=303,
        )
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": "用户名或密码错误",
        },
        status_code=401,
    )


@router.get("/logout")
async def logout (request:Request):
    #清除登录状态并返回登陆界面
    request.session.clear()

    return RedirectResponse(
        url="/login",
        status_code=303
    )
