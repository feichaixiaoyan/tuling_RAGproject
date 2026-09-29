from mildoc_index.parser.document_parser import DocumentParser
from mildoc_index.logger.logger import setup_logging
from markitdown import MarkItDown
from io import BytesIO

logger=setup_logging(__name__)  # 设置日志等级为 INFO
class OfficeParser(DocumentParser):

    #这几个类型是minio那边传过来的 类型
    supported_content_types = {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    def _init__(self):
        self.markdown_parser = MarkItDown()  # 初始化 MarkdownParser 实例
    def parser(self, data: bytes) -> str:
        """
        解析 Office 文件内容并返回文本。

        Args:
            data (bytes): Office 文件内容的二进制数据。

        Returns:
            str: Office 文件内容的文本表示。
        """
        # 这里可以使用第三方库来解析 Office 文件 将office文件转为markitdown格式 在进行转文字 
        file_stream=BytesIO(data)
        try:
            # 转为markdown 然后取出它里面的文字内容
            result = self.markdown_parser.convert_stream(file_stream)  # 使用 MarkItDown
            if result and hasattr(result, "text_content"):
                return result.text_content.strip()
            #不满足条件 解析异常 或者不满足体哦阿健  # 返回转换后的 Markdown 文本
            logger.error("Office 文档解析结果为空或格式异常")
            return ""
        except Exception as e:
            logger.error(f"officce文档解析失败{e}")
            return ""


    def supports(self, contentype: str) -> bool:
        return contentype in self.supported_content_types
        
       