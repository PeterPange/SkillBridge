"""知识库爬虫:抓取课程源站内容,补充 RAG 知识库。

当前支持 Microsoft Learn 课程页(项目课程数据的源头),
产出标题级结构的 Markdown,直接可被 rag 管线入库。
"""

from crawler.models import CrawledDoc

__all__ = ["CrawledDoc"]
