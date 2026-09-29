from mildoc_index.parser.document_parser import DocumentParser
# from mildoc_index.logger.logger import setup_logging


class TextParser(DocumentParser):
    # 文件从 MinIO、OSS 或上传接口读出来时，拿到的通常都是二进制数据
    supported_content_types={
        "text/plain",
        "text/csv",
        "text/markdown",
    }
    
    def parse(self, data: bytes) -> str:
        """
        解析文本文件内容并返回文本。

        Args:
            data (bytes): 文本文件内容的二进制数据。

        Returns:
            str: 文本文件内容的文本表示。
        """
        return data.decode('utf-8',errors='ignore')  # 忽略解码错误，返回可解码的部分

    def supports(self, content_type: str) -> bool:
        
        # 简单判断是否为文本文件，可以根据需要进行更复杂的判断
        return content_type in self.supported_content_types

if __name__ == "__main__":
    # 测试 TextParser
    parser = TextParser()
    
    # 测试 parse 方法
    sample_text = b"Hello, this is a sample text file." #注意这里有个b 表示二进制的数据 
    parsed_text = parser.parse(sample_text)
    print("Parsed Text:", parsed_text)
    
    # 测试 supports 方法
    print("Supports 'text/plain':", parser.supports("text/plain"))  # True
    print("Supports 'application/pdf':", parser.supports("application/pdf"))  # False