"""共享知识库问答 API(员工与 HR 都可用)。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from webapp.services.viewmodels import AnswerView

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(req: AskRequest) -> dict:
    """知识库问答:返回产品化回答(段落 + 来源,隐藏向量得分)。"""
    from rag.pipeline import RagPipeline

    pipeline = RagPipeline()
    result = pipeline.query(req.question, top_k=3)
    passages = []
    for c in result.chunks:
        chunk = c.chunk
        passages.append(
            {
                "doc_title": chunk.doc_title,
                "heading": " / ".join(chunk.heading_path),
                "content": chunk.content,
                "source_name": str(chunk.source).rsplit("/", 1)[-1],
            }
        )
    view = AnswerView(question=req.question, passages=passages)
    return {
        "question": view.question,
        "passages": [
            {
                "doc_title": p["doc_title"],
                "heading": p["heading"],
                "content": p["content"],
                "source_name": p["source_name"],
            }
            for p in view.passages
        ],
        "answered": bool(passages),
    }
