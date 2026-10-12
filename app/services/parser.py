"""文件解析：所有格式 → Markdown，使用 Docling 引擎。

完全照搬 surfsense_local/backend/worker/ingestion/parsing.py 的写法。
Docling 是统一的文档解析引擎，支持 PDF/DOCX/PPTX/XLSX/HTML/CSV/MD/IMAGE。
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# 已经是文本格式，直接读盘，不经过 Docling
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".text"}


class UnreadableFileError(Exception):
    """Docling 无法加载的文件，重试也无意义。"""
    pass


def markdown_for(path: Path) -> str:
    """将任意格式文档转为 Markdown 字符串。

    Args:
        path: 文件路径

    Returns:
        Markdown 格式的纯文本

    Raises:
        UnreadableFileError: 文件无法读取或格式不支持
        FileNotFoundError: 文件在磁盘上不存在
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")

    converted = convert(path)
    return converted.export_to_markdown()


def convert(path: Path) -> Any:
    """用 Docling 解析文件，返回 DoclingDocument。

    Args:
        path: 文件路径

    Returns:
        DoclingDocument 对象，调用 .export_to_markdown() 得到 Markdown

    Raises:
        UnreadableFileError: Docling 无法打开文件
    """
    converter = _get_converter()
    from docling.exceptions import ConversionError, DocumentLoadError

    try:
        result = converter.convert(path)
        return result.document
    except ConversionError as refused:
        # Docling 报告文件无法打开或模型内存不足，统一处理
        if isinstance(refused.__cause__, DocumentLoadError):
            raise UnreadableFileError(str(refused)) from refused
        raise


@lru_cache(maxsize=1)
def _get_converter() -> Any:
    """懒加载 Docling DocumentConverter，每个进程只创建一次。

    源码注释说明：
      - 首次转换时会加载模型，成本约数秒
      - torch 由 Docling 间接引入，API 进程不需要，但 Worker 进程需要
      - 使用 CPU-only 版本（不装 CUDA）
    """
    # 设置 HuggingFace 缓存目录（可选，默认在 ~/.cache/huggingface）
    hf_home = Path.home() / ".cache" / "huggingface"
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # 离线模式，避免每次启动检查更新

    # 懒加载：只在首次调用时 import
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter

    # PDF 解析选项：启用 OCR 和表格结构识别
    options = PdfPipelineOptions()
    options.do_ocr = True
    options.do_table_structure = True

    # 线程数：取物理核心数，最多 8（与源码一致）
    num_threads = min(8, psutil.cpu_count(logical=False) or 4)
    options.accelerator_options = AcceleratorOptions(num_threads=num_threads)

    return DocumentConverter(
        allowed_formats=[
            InputFormat.PDF,
            InputFormat.DOCX,
            InputFormat.PPTX,
            InputFormat.XLSX,
            InputFormat.HTML,
            InputFormat.CSV,
            InputFormat.MD,
            InputFormat.IMAGE,
        ],
        format_options={
            InputFormat.PDF: PdfPipelineOptions(pipeline_options=options),
        },
    )


async def parse_document(path: Path) -> str:
    """异步包装：在线程池中运行同步的 Docling 解析。

    Docling 的解析是 CPU 密集型操作，放在线程池避免阻塞事件循环。
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, markdown_for, path)