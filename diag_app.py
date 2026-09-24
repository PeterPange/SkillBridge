"""一次性诊断:在 uvicorn 环境里复现 sentence-transformers 导入问题。"""
import sys
import traceback
from pathlib import Path

from fastapi import FastAPI

app = FastAPI()


@app.get("/diag")
def diag():
    project_root = Path("/home/panjinhui/code/SkillBridge").resolve()
    path_entries = []
    for entry in list(sys.path):
        try:
            resolved = Path(entry).resolve() if entry else Path.cwd().resolve()
        except OSError:
            resolved = None
        path_entries.append((entry, str(resolved), resolved == project_root))

    try:
        from skill_normalization import matcher

        matcher._import_sentence_transformers()
        encoder = matcher.default_encoder()
        return {
            "encoder": type(encoder).__name__,
            "model": getattr(encoder, "model_name", None),
            "path_entries": path_entries,
        }
    except Exception:
        return {"error": traceback.format_exc(), "path_entries": path_entries}
