import os 
from dotenv import load_dotenv
from openai import OpenAI
from mildoc_index.logger.logger import setup_logging

load_dotenv()
logger=setup_logging(__name__)

class EmbeddingTool:
    def __init__(self) -> None:
        self.client=OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
        self.model_name=os.getenv("EMBEDDING_MODEL")
        self.dimension=os.getenv("MILVUS_VECTOR_DIM")

        if not all([self.client, self.model_name, self.dimension]):
                raise ValueError(
                    "Embedding 配置不完整，请检查 "
                    "OPENAI_API_KEY、OPENAI_BASE_URL、"
                    "EMBEDDING_MODEL 和 MILVUS_VECTOR_DIM"
                )
        logger.info("EmbeddingTool 初始化成功，配置完整。")
    #文本转向量
    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        获取文本的向量表示。

        Args:
            texts (list[str]): 文本列表
        返回的响应示例：
                    {
            "data": [
                {
                "index": 0,
                "embedding": [0.12, -0.35, 0.08]
                }
            ],
            "model": "你的向量模型",
            "usage": {
                "prompt_tokens": 8,
                "total_tokens": 8
            }
            }
        Returns:
            list[list[float]]: 每个文本的向量表示。
        """
        #openai的embedding 不接受空文本向量
        if not texts or any(not text.strip() for text in texts):
            logger.error("输入文本列表为空或包含空字符串。")
            return []
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=  texts,
                dimensions=int(self.dimension),
                encoding_format="float"
            )

            if not response.data:
                 logger.error("模型没有返回向量数据。")
                 return []
            embeddings=[item.embedding for item in response.data]
            #验证维度信息
            if len(response.data[0].embedding) != int(self.dimension):
                logger.error(
                    f"返回的向量维度与配置不匹配。预期: {self.dimension}, 实际: {len(response.data[0].embedding)}"
                )
                return []
            if len(embeddings)!=len(texts):
                logger.error(
                    f"返回的向量数量与输入文本数量不匹配。预期: {len(texts)}, 实际: {len(embeddings)}"
                )
                return []
            return embeddings
        except Exception as e:
            logger.exception(f"获取文本向量失败: {e}")
            return []

if __name__ == "__main__":
    embedding_tool = EmbeddingTool()

    texts = ["这是第一段测试文字。", "这是第二段测试文字。"]
    vectors = embedding_tool.get_embeddings(texts)

    print("输入文本数量：", len(texts))
    print("返回向量数量：", len(vectors))
    if vectors:
        print("每条向量的维度：", len(vectors[0]))
    