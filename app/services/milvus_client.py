
"""Milvus 向量数据库客户端。

负责：
1. 连接 Milvus 服务
2. 创建和加载向量集合
3. 插入文档切片及其向量
4. 根据问题向量检索相关文档
5. 删除整个向量集合
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.config import config


# 获取当前模块的日志记录器，用于记录连接、建表等信息
logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """封装一次向量检索命中的结果。"""

    id: int              # Milvus 中当前 Chunk 的主键
    score: float         # 向量相似度分数
    chunk_text: str      # 命中的文本切片
    document_id: int     # 该切片所属的原始文档 ID


class MilvusClient:
    """封装 Milvus 的连接、数据插入和向量检索操作。"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = None,
        dimension: int = None,
    ):
        # 优先使用调用者传入的参数，否则读取项目配置
        self.host = host or config.MILVUS_HOST
        self.port = port or config.MILVUS_PORT

        # Milvus 集合名称，类似于关系型数据库中的表名
        self.collection_name = collection_name or config.COLLECTION_NAME

        # 向量维度必须与 Embedding 模型输出的维度一致
        self.dimension = dimension or config.EMBEDDING_DIM

        # 保存集合对象；初始化时还没有获取集合
        self._collection: Collection | None = None

    def connect(self) -> None:
        """连接 Milvus 服务。"""

        # default 是当前连接的别名，后续操作可以使用这个连接
        connections.connect(
            "default",
            host=self.host,
            port=self.port,
        )

        logger.info(
            f"Connected to Milvus at {self.host}:{self.port}"
        )

    def _ensure_collection(self) -> None:
        """确保集合存在，并且已经加载，可以进行搜索。"""

        # 检查指定名称的集合是否已经存在
        if utility.has_collection(self.collection_name):

            # 获取已有集合对象
            self._collection = Collection(self.collection_name)

            # 将集合加载到查询资源中，供向量搜索使用
            self._collection.load()

            # 集合已经存在，不需要重复创建
            return

        # 集合不存在时，定义集合中的字段
        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.INT64,
                is_primary=True,  # 设置为主键
                auto_id=True,     # 主键由 Milvus 自动生成
            ),
            FieldSchema(
                name="vector",
                dtype=DataType.FLOAT_VECTOR,  # 浮点数向量
                dim=self.dimension,           # 向量维度
            ),
            FieldSchema(
                name="document_id",
                dtype=DataType.INT64,  # 原始文档 ID
            ),
            FieldSchema(
                name="chunk_text",
                dtype=DataType.VARCHAR,  # 保存文本切片
                max_length=2000,         # 字符串最大长度
            ),
            FieldSchema(
                name="workspace_id",
                dtype=DataType.INT64,  # 工作空间 ID，用于数据隔离
            ),
        ]

        # 将所有字段组合成集合的 Schema（结构定义）
        schema = CollectionSchema(
            fields,
            description="Document chunks embedding collection",
        )

        # 根据 Schema 创建 Milvus 集合
        self._collection = Collection(
            self.collection_name,
            schema,
        )

        # 为 vector 字段创建向量索引
        self._collection.create_index(
            field_name="vector",
            index_params={
                # IVF_FLAT：通过聚类桶缩小搜索范围，再进行精确距离计算
                "index_type": "IVF_FLAT",

                # IP 表示 Inner Product，即内积
                "metric_type": "IP",

                # nlist 表示索引建立时的聚类桶数量
                "params": {"nlist": 128},
            },
        )

        # 加载集合，供后续向量搜索使用
        self._collection.load()

        logger.info(f"Created collection {self.collection_name}")

    def upsert(
        self,
        document_id: int,
        chunk_text: str,
        vector: list[float],
        workspace_id: int,
    ) -> int:
        """插入一条文档切片记录，返回 Milvus 自动生成的主键。

        注意：当前实现调用的是 insert()，并非真正的 upsert()。
        如果需要更新已有记录，应另外实现更新或 Upsert 逻辑。
        """

        # 确保集合已经创建并加载
        self._ensure_collection()

        # 使用字典指定字段和值，避免字段顺序不匹配的问题
        # id 设置了 auto_id=True，因此这里不需要传入 id
        data = [
            {
                "vector": vector,
                "document_id": document_id,
                "chunk_text": chunk_text,
                "workspace_id": workspace_id,
            }
        ]

        # 将记录插入 Milvus
        result = self._collection.insert(data)

        # 返回 Milvus 自动生成的主键
        return result.primary_keys[0]

    def search(
        self,
        query_vector: list[float],
        workspace_id: int | None = None,
        top_k: int = None,
    ) -> list[SearchResult]:
        """根据问题向量搜索最相关的文档切片。"""

        # 确保集合已经创建并加载
        self._ensure_collection()

        # 如果调用者没有指定返回数量，则使用配置中的默认值
        top_k = (
            top_k
            if top_k is not None
            else config.SEARCH_TOP_K
        )

        # 如果指定了工作空间，只检索该工作空间的数据
        # 使用 is not None，避免 workspace_id=0 时过滤失效
        expr = (
            f"workspace_id == {workspace_id}"
            if workspace_id is not None
            else ""
        )

        # 执行向量相似度搜索
        results = self._collection.search(
            # 查询向量需要放在列表中；列表中的每个向量代表一次查询
            data=[query_vector],

            # 指定需要搜索的向量字段
            anns_field="vector",

            # 搜索参数
            param={
                # 必须与所使用的索引和距离度量配置保持一致
                "metric_type": "IP",

                # nprobe 表示每次搜索探测多少个聚类桶
                # 数值越大，通常召回率越高，但搜索开销也可能增加
                "params": {"nprobe": 16},
            },

            # 最多返回多少条命中结果
            limit=top_k,

            # 工作空间过滤条件；空字符串表示不添加该过滤条件
            expr=expr,

            # 除主键和分数外，还需要返回的字段
            output_fields=["chunk_text", "document_id"],
        )

        # 将 Milvus 原始结果转换成项目统一使用的 SearchResult
        items = []

        # results 中每个 hits 对应一次查询的命中列表
        for hits in results:
            for hit in hits:

                # hit.id：命中记录的主键
                # hit.score：相似度分数
                # hit.entity：命中记录中要求返回的字段
                items.append(
                    SearchResult(
                        id=hit.id,
                        score=hit.score,
                        chunk_text=hit.entity.get("chunk_text"),
                        document_id=hit.entity.get("document_id"),
                    )
                )

        # 返回整理好的检索结果列表，供 RAG 流程使用
        return items

    def drop_collection(self) -> None:
        """删除整个集合及其包含的数据，请谨慎调用。"""

        # 只有集合存在时才执行删除
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)


# 全局客户端缓存，初始时尚未创建客户端
_milvus: MilvusClient | None = None


def get_milvus() -> MilvusClient:
    """获取全局 Milvus 客户端，首次调用时创建并连接。"""

    global _milvus

    # 首次调用时，创建客户端并建立连接
    if _milvus is None:
        _milvus = MilvusClient()
        _milvus.connect()

    # 后续调用直接复用已有客户端
    return _milvus
