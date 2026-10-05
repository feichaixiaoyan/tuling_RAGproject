from abc import ABC, abstractmethod

"""
这是一个解析器的规范类 
这个文件现在不负责真正解析 PDF 或 Word，它只是在提前规定：
1. 每个解析器都必须有 parse() 方法，用来把文件内容转成文字。

2. 每个解析器都必须有 supports() 方法，用来判断它能不能处理当前文件类型。
"""

class DocumentParser(ABC):
    #所有解析器都应该遵守的规则 


    @abstractmethod
    def parse(self, data: bytes) -> str:
        """
        解析文件内容并返回文本。

        Args:
            data (bytes): 文件内容的二进制数据。

        Returns:
            str: 文件内容的文本表示。
        """
        raise NotImplementedError

    @abstractmethod
    def supports(self, content_type: bytes) -> bool:
        """
        判断解析器是否支持处理给定的文件类型。

        Args:
            data (bytes): 文件内容的二进制数据。

        Returns:
            bool: 如果支持处理该文件类型，返回 True；否则返回 False。
        """
        raise NotImplementedError