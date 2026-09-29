from typing import Optional
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
        self.parser=[MarkdownParser,TextParser,OfficeParser,PDFParser,NoneParser]  # 解析器列表，NoneParser放在最后作为兜底解析器)]

    def add_parser(self,parser:DocumentParser):
        # 可以在这里添加新的解析器,以后入股需要添加解析器的话 就不需要不用修改 self.parsers 那一大段注册列表，直接调用它即可。 

        self.parser.append(parser)

    def get_parser(self, content_type: str) -> Optional[DocumentParser]:
        """
        根据文件的 MIME 类型选择合适的解析器。

        Args:
            content_type (str): 文件的 MIME 类型。

        Returns:
            Optional[DocumentParser]: 如果找到合适的解析器，返回该解析器实例；否则返回 None。
        """
        for parser in self.parser:
            if parser().supports(content_type):
                return parser

        return None  # 如果没有找到合适的解析器，返回 None

    def extract_minio_name(self,object_name:str)->str:
        """
        从 MinIO 对象名称中提取文件名。

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
        if content_type:
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

        return type_mapping.get(content_type.lower(),content_type.strip("/")[-1].lower())

    def calculate_md5(self,data:bytes):

        #计算文件的MD5值 给文件内容计算一个唯一指纹 后续如果文件的内容一样 就会得到相同的MD5值 
        #可以用它判断是否上传了同一个文件   文件内容是否变化 
        md5=hashlib.md5()
        md5.update(data)
        return md5.hexdigest()  # 返回十六进制的 MD5 值
    
    def split_text_by_langchain(self,text:str)->list[str]:
