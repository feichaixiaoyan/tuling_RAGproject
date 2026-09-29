from mildoc_index.parser.document_parser import DocumentParser
from mildoc_index.logger.logger import setup_logging


logger=setup_logging(__name__)  # 设置日志等级为 INFO

class MarkdownParser(DocumentParser):
    supported_content_types = {
        "text/markdown",
        "text/x-markdown",
        "application/markdown",
        "md",
    }

    def parse(self, data: bytes) -> str:
        #markdown 也有多种格式的编码方式 
        encoding_way=["utf-8", "gbk", "gb2312", "latin-1"]
        for i in encoding_way:
            try:
                return data.decode(i)
            except UnicodeDecodeError:
                continue
        
        logger.warning("无法解码 Markdown 文件内容，尝试使用 'utf-8' 解码。")
        return data.decode("utf-8", errors="ignore")  # 忽略解码错误，返回可解码的部分
    def supports(self, content_type: str) -> bool:
        """
        判断解析器是否支持处理给定的 Markdown 文件类型。

        Args:
            content_type (str): Markdown 文件的 MIME 类型。

        Returns:
            bool: 如果支持处理该文件类型，返回 True；否则返回 False。
        """
        return content_type in self.supported_content_types