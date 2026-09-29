from PyPDF2 import PdfReader
from mildoc_index.parser.document_parser import DocumentParser
from io import BytesIO 
from mildoc_index.logger.logger import setup_logging


logger=setup_logging(__name__)  # 设置日志等级为 INFO
class PDFParser(DocumentParser):
    supported_content_types = {
        "application/pdf",
    }

    def parse(self, data: bytes) -> str:
        """
        解析 PDF 文件内容并返回文本。

        Args:
            data (bytes): PDF 文件内容的二进制数据。

        Returns:
            str: PDF 文件内容的文本表示。
        """
        try:
            # 使用 PdfReader 读取 PDF 数据
            reader = PdfReader(BytesIO(data)) #把数据临时包装成一个文件对象 

            page_text=[]

            for page in reader.pages:
                #依次读取每一页当中的内容 进行提取文字
                page_text.append(page.extract_text() or "")  # 提取文本，如果为空则添加空字符串
            return "\n".join(page_text)
        
        except Exception as error:
            logger.error("PDF 解析失败",error)
            raise 

    def supports(self, content_type: str) -> bool:
        """
        判断解析器是否支持处理给定的 PDF 文件类型。

        Args:
            content_type (str): PDF 文件的 MIME 类型。

        Returns:
            bool: 如果支持处理该文件类型，返回 True；否则返回 False。
        """
        return content_type in self.supported_content_types

if __name__ == '__main__':
    from pathlib import Path
    data = Path('mildoc_index/data/Git讲义.pdf').read_bytes()
    pdfparser=PDFParser()
    text=pdfparser.parse(data)
    print(text)