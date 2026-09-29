from mildoc_index.logger.logger import setup_logging
from mildoc_index.parser.document_parser import DocumentParser

"""
这个是最后兜底的解析器 怕文件遇到不支持的类型报错 
比如 .zip / .exe / 不认识的文件类型
"""
logger=setup_logging(__name__)  # 设置日志等级为 INFO

class NoneParser(DocumentParser):
    
    def parse(self, data: bytes) -> str:
        """
        解析未知文件类型的内容并返回文本。

        Args:
            data (bytes): 未知文件类型的二进制数据。

        Returns:
            str: 未知文件类型的文本表示。
        """
        logger.info("当前文件没有可用解析器，返回空字符串")
        return ""  # 返回空字符串，表示无法解析

    def supports(self, content_type: str) -> bool:
        #默认接受任何文件类型 
        return True