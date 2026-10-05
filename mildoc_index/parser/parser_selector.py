from typing import Optional,Any
from minio import Minio
from mildoc_index.parser.document_parser import DocumentParser
from mildoc_index.parser.markdown_parser import MarkdownParser
from mildoc_index.parser.none_parser import NoneParser
from mildoc_index.parser.office_parser import OfficeParser
from mildoc_index.parser.pdf_parser import PDFParser
from mildoc_index.parser.text_parser import TextParser
import os
import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter
from mildoc_index.logger.logger import setup_logging

logger = setup_logging(__name__)

class Parser_Selector:
    # 选择合适的解析器来处理不同类型的文件
    def __init__(self,
        minio_client:Minio, 
        chunk_size: int = 2048,
        overlap_size: int = 128):

        self.minio_client = minio_client
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        #这是有顺序的 让none_parser来进行兜底
        self.parser=[MarkdownParser(),TextParser(),OfficeParser(),PDFParser(),NoneParser()]  # 解析器列表，NoneParser放在最后作为兜底解析器)]

    def add_parser(self,parser:DocumentParser):
        # 可以在这里添加新的解析器,以后入股需要添加解析器的话 就不需要不用修改 self.parsers 那一大段注册列表，直接调用它即可。 

        self.parser.insert(-1, parser)

    def get_parser(self, content_type: str) -> Optional[DocumentParser]:
        """
        根据文件的 MIME 类型选择合适的解析器。

        Args:
            content_type (str): 文件的 MIME 类型。

        Returns:
            Optional[DocumentParser]: 如果找到合适的解析器，返回该解析器实例；否则返回 None。
        """
        for parser in self.parser:
            if parser.supports(content_type):
                return parser

        return None  # 如果没有找到合适的解析器，返回 None

    def extract_minio_name(self,object_name:str)->str:
        """
        从 MinIO 对象名称中提取文件名。
        例如：knowledge/git/第一章.pdf   第一章.pdf

        Args:
            object_name (str): MinIO 对象的完整名称。

        Returns:
            str: 提取出的文件名。
        """
        
        return os.path.basename(object_name)  # 使用 os.path.basename 提取文件名

    def mime_to_doctype(self,content_type):
        """
        把 MIME 类型转换成简短的文件类型名称。
        """
        if not content_type :
            return ""
        
        #字典映射对象 
        type_mapping = {
        "application/pdf": "pdf",
        "text/plain": "txt",
        "text/markdown": "md",
        "text/x-markdown": "md",
        "application/markdown": "md",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-powerpoint": "ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    }

        return type_mapping.get(content_type.lower(),content_type.split("/")[-1].lower(),)

    def calculate_md5(self,data:bytes):

        #计算文件的MD5值 给文件内容计算一个唯一指纹 后续如果文件的内容一样 就会得到相同的MD5值 
        #可以用它判断是否上传了同一个文件   文件内容是否变化 
        #hashlib当中有很多算法 先初始化一个md5对象 然后调用update方法传入数据 最后调用hexdigest方法得到十六进制的MD5值
        md5=hashlib.md5()
        md5.update(data)
        return md5.hexdigest()  # 返回十六进制的 MD5 值
    
    def split_text_by_langchain(self,text:str)->list[str]:
        """
        使用 langchain 的 RecursiveCharacterTextSplitter 将文本分割成多个块。

        Args:
            text (str): 要分割的文本。

        Returns:
            list[str]: 分割后的文本块列表。
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.overlap_size,
            length_function=len,
            separators = ["\n\n", "\n", "。", "！", "？", "，", " ", ""]

        )
        splited_texts = text_splitter.split_text(text)
        return splited_texts

    def process_text_from_minio(self, bucket_name: str, object_name: str) -> dict[str, Any] | None:
        """
        从 MinIO 中获取文本文件内容，并将其分割成多个块。

        Args:
            bucket_name (str): MinIO 存储桶名称。
            object_name (str): 在minio当中的文件路径。
            例如 
            bucket_name = "mildoc1"
            object_name = "documents/git/git教程.pdf"""
        response = None  # 初始化 response 变量
        try:
            #1.这里这是拿到了文件的信息卡 
                    stat = self.minio_client.stat_object(bucket_name, object_name)
                    max_size = 512 * 1024 * 1024
            
                    file_size = stat.size
                    if file_size is None:
                        logger.warning("无法获取文件大小，跳过文件：%s", object_name)
                        return None
            
                    if file_size > max_size:
                        logger.warning("文件 %s 大小超过 512 MB，跳过处理", object_name)
                        return None
                    
                    #2.从minio上下载文件内容
                    # 这一步相当于去给minio发送网络请求
                    response = self.minio_client.get_object(bucket_name, object_name)
                    data:bytes = response.read()  # 读取文件内容
                    header = response.headers
                    #响应头当中的Content-Type 存放的是文件的 MIME 类型  ----->是为了后续parser的选择 
                    content_type = header.get("Content-Type", "")
            
                    #3.根据文件的MIME类型选择合适的解析器
                    
                    doc_name=self.extract_minio_name(object_name) 
                    doc_type=self.mime_to_doctype(content_type)
                    doc_md5=self.calculate_md5(data)
                    doc_length = len(data)
                    
                    parser = self.get_parser(content_type)
            
                    if parser is None:
                        logger.warning("未找到适合的解析器，跳过文件：%s", content_type)
                        return None
                    #s% 是占位符的意思 
                    logger.info("开始解析文件：%s，使用解析器：%s",object_name, parser.__class__.__name__)
            
                    #4.使用解析器解析文件内容
                    parsed_text: str = parser.parse(data)
            
                    #空的文本内容不需要进行后续处理
                    if not parsed_text.strip():
                        logger.warning("文件 %s 解析后内容为空，跳过处理", object_name)
                        return None
            
                    #5.使用 langchain 的 RecursiveCharacterTextSplitter 将文本分割成多个块
                    splited_texts:list[str] = self.split_text_by_langchain(parsed_text)
                    #返回后续向量化需要的信息 
                    return{
                        "doc_name": doc_name,#文件的名字 Git教程.pdf
                        "doc_path_name": object_name, #文件的路径：documents/git/Git教程.pdf
                        "doc_type": doc_type,#文件的类型：pdf
                        "doc_md5": doc_md5, #文件的MD5值 4f9c12b64ae88d47d2d175c1a4c734a2
                        "doc_length": doc_length, #这个是文件的大小 
                        "splited_texts": splited_texts 
                    }

        except Exception as e:
            logger.error("解析文件 %s 时发生错误：%s", object_name, str(e))
            return None
        finally:
            if response:
                response.close() #关闭网络连接 释放资源
                response.release_conn()
        



