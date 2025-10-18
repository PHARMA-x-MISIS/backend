# server.py
import os
import json
import time
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import joblib
import numpy as np
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ================================
# Config
# ================================
# Модель и метки

# server.py (вверху, после импортов)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(".env"))  # .env в корне проекта
except Exception:
    pass

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts")).expanduser().resolve()
DEFAULT_THR = float(os.getenv("DEFAULT_THR", "0.5"))

# Внешний API каталога (для рекомендаций)
MP_API_BASE = os.getenv("MP_API_BASE", "https://mosprom.misis-team.ru").rstrip("/")
MP_API_TIMEOUT = float(os.getenv("MP_API_TIMEOUT", "8.0"))
MP_API_PAGE_LIMIT = int(os.getenv("MP_API_PAGE_LIMIT", "100"))
MP_API_TOKEN = os.getenv("MP_API_TOKEN", "")
MP_API_HEADERS = {"accept": "application/json"}
if MP_API_TOKEN:
    MP_API_HEADERS["Authorization"] = f"Bearer {MP_API_TOKEN}"

# Кэширование списков сообществ/постов
CACHE_TTL_SEC = int(os.getenv("MP_API_CACHE_TTL", "60"))

# ================================
# App
# ================================
app = FastAPI(title="ML Service (simple)", version="1.1")

# ================================
# Globals
# ================================
PIPE = None                # sklearn Pipeline
LABELS: List[str] = []     # порядок меток (из labels.json)
THRESHOLDS = None          # np.ndarray [L] или None

_cache_comm: Dict[str, Any] = {"ts": 0.0, "items": []}
_cache_posts: Dict[str, Any] = {"ts": 0.0, "items": []}

# ================================
# Utils: normalization
# ================================
def _normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.replace("ё", "е")
    return s.strip()

def _norm_token(t: str) -> str:
    if not isinstance(t, str):
        return ""
    s = unicodedata.normalize("NFC", t).strip().lower()
    s = s.replace("ё", "е")
    synonyms = {
        "cpp": "c++",
        "c plus plus": "c++",
        "c-плюс-плюс": "c++",
        "си": "c",
        "js": "javascript",
    }
    return synonyms.get(s, s)

def _norm_list(xs: List[str]) -> List[str]:
    out, seen = [], set()
    for x in xs or []:
        n = _norm_token(x)
        if n and n not in seen:
            out.append(n)
            seen.add(n)
    return out

# ================================
# Artifacts loading (ML)
# ================================
def load_artifacts():
    """Load sklearn pipeline, labels, optional thresholds."""
    global PIPE, LABELS, THRESHOLDS
    print(f"[INFO] Using ARTIFACTS_DIR = {ARTIFACTS_DIR}")
    model_path = ARTIFACTS_DIR / "tfidf_logreg_ovr.joblib"
    labels_path = ARTIFACTS_DIR / "labels.json"
    thr_path = ARTIFACTS_DIR / "thresholds.npy"

    missing = [p.name for p in (model_path, labels_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Не найдены артефакты: {', '.join(missing)} в {ARTIFACTS_DIR}.\n"
            "Ожидается структура:\n"
            "  artifacts/\n"
            "    tfidf_logreg_ovr.joblib\n"
            "    labels.json\n"
            "    (опц.) thresholds.npy\n"
            "Или укажи путь через переменную ARTIFACTS_DIR."
        )

    PIPE = joblib.load(model_path)
    LABELS = json.loads(labels_path.read_text(encoding="utf-8"))

    if thr_path.exists():
        THRESHOLDS = np.load(thr_path)
        if THRESHOLDS.shape != (len(LABELS),):
            print("[WARN] thresholds.npy не совпадает по размеру с labels.json — игнорирую")
            THRESHOLDS = None
    else:
        THRESHOLDS = None

# ================================
# ML predict
# ================================
class PredictRequest(BaseModel):
    description: str

def predict_labels(description: str) -> List[str]:
    if PIPE is None or not LABELS:
        load_artifacts()

    text = _normalize_text(description or "")
    if not text:
        return []

    scores = PIPE.decision_function([text])   # (1, L)
    probs = 1.0 / (1.0 + np.exp(-scores))[0]  # (L,)
    thresholds = THRESHOLDS if THRESHOLDS is not None else np.full(len(LABELS), DEFAULT_THR, dtype=float)

    idx = np.where(probs >= thresholds)[0]
    if idx.size == 0:
        return []
    idx_sorted = idx[np.argsort(-probs[idx])]
    return [LABELS[i] for i in idx_sorted]

@app.post("/predict", response_model=List[str])
def predict(req: PredictRequest) -> List[str]:
    try:
        return predict_labels(req.description)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

@app.get("/")
def ping():
    return {"status": "ok"}

# ================================
# External API clients (catalog)
# ================================
async def _get_all(endpoint: str) -> List[Dict[str, Any]]:
    """GET paginate: /communities/ or /posts/ using aiohttp"""
    items = []
    skip = 0
    timeout = aiohttp.ClientTimeout(total=MP_API_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            url = f"{MP_API_BASE}/{endpoint}?skip={skip}&limit={MP_API_PAGE_LIMIT}"
            async with session.get(url, headers=MP_API_HEADERS) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise HTTPException(status_code=resp.status, detail=f"API error: {text}")
                try:
                    page = await resp.json()
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Invalid json from API: {e}")
                if not isinstance(page, list):
                    break
                items.extend(page)
                if len(page) < MP_API_PAGE_LIMIT:
                    break
                skip += MP_API_PAGE_LIMIT
    return items

async def _get_communities() -> List[Dict[str, Any]]:
    now = time.time()
    if now - _cache_comm["ts"] > CACHE_TTL_SEC:
        _cache_comm["items"] = await _get_all("communities/")
        _cache_comm["ts"] = now
    return _cache_comm["items"]

async def _get_posts() -> List[Dict[str, Any]]:
    now = time.time()
    if now - _cache_posts["ts"] > CACHE_TTL_SEC:
        _cache_posts["items"] = await _get_all("posts/")
        _cache_posts["ts"] = now
    return _cache_posts["items"]

# ================================
# Reco: one-hot + cosine
# ================================
def _build_vocab(objects: List[Dict[str, Any]]) -> Dict[str, int]:
    """Collect all skills from objects into vocab {token: index}."""
    vocab: Dict[str, int] = {}
    for obj in objects:
        for tok in _norm_list(obj.get("skills", [])):
            if tok not in vocab:
                vocab[tok] = len(vocab)
    return vocab

def _one_hot_matrix(objects: List[Dict[str, Any]], vocab: Dict[str, int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (M, ids, popularity). M: [N,L] one-hot in vocab space."""
    L = len(vocab)
    if not objects or L == 0:
        return np.zeros((0, 0), dtype=np.float32), np.zeros((0,), dtype=np.int64), np.zeros((0,), dtype=np.float32)

    M = np.zeros((len(objects), L), dtype=np.float32)
    ids = np.zeros((len(objects),), dtype=np.int64)
    pop = np.zeros((len(objects),), dtype=np.float32)

    for i, obj in enumerate(objects):
        ids[i] = int(obj.get("id", 0))
        pop[i] = float(obj.get("member_count", obj.get("like_count", 0)) or 0)
        for tok in _norm_list(obj.get("skills", [])):
            j = vocab.get(tok)
            if j is not None:
                M[i, j] = 1.0
            # мягкий авто-хинт для школьной электроники:
            if tok == "arduino":
                jcpp = vocab.get("c++")
                if jcpp is not None:
                    M[i, jcpp] = 1.0
    return M, ids, pop

def _skills_to_vec(skills: List[str], vocab: Dict[str, int]) -> np.ndarray:
    v = np.zeros((len(vocab),), dtype=np.float32)
    for tok in _norm_list(skills):
        j = vocab.get(tok)
        if j is not None:
            v[j] = 1.0
        # полезные хинты
        if tok in ("arduino", "олимпиадная информатика", "codeforces"):
            jcpp = vocab.get("c++")
            if jcpp is not None:
                v[jcpp] = 1.0
    return v

def _cosine_scores(user_vec: np.ndarray, M: np.ndarray) -> np.ndarray:
    if M.size == 0:
        return np.zeros((0,), dtype=np.float32)
    un = np.linalg.norm(user_vec)
    if un == 0.0:
        return np.zeros((M.shape[0],), dtype=np.float32)
    dots = M @ user_vec
    norms = np.linalg.norm(M, axis=1) * un
    norms[norms == 0.0] = 1e-8
    return (dots / norms).astype(np.float32)

# ================================
# Schemas for reco
# ================================
class RecoRequest(BaseModel):
    skills: List[str]
    limit: Optional[int] = 50

class RecoResponseItem(BaseModel):
    id: int
    score: float

# ================================
# Endpoints: recommendations
# ================================
@app.post("/predict_communities", response_model=List[RecoResponseItem])
async def predict_communities(req: RecoRequest) -> List[RecoResponseItem]:
    try:
        objs = await _get_communities()
        vocab = _build_vocab(objs)
        M, ids, pop = _one_hot_matrix(objs, vocab)
        u = _skills_to_vec(req.skills, vocab)
        scores = _cosine_scores(u, M)
        if scores.size == 0:
            return []
        # сортировка: по score (cosine) ↓, тай-брейк — по популярности ↓
        order = np.lexsort((-pop, -scores))
        k = max(1, int(req.limit or 50))
        idx = order[:k]
        return [RecoResponseItem(id=int(ids[i]), score=float(scores[i])) for i in idx]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

@app.post("/predict_posts", response_model=List[RecoResponseItem])
async def predict_posts(req: RecoRequest) -> List[RecoResponseItem]:
    try:
        objs = await _get_posts()
        vocab = _build_vocab(objs)
        M, ids, pop = _one_hot_matrix(objs, vocab)
        u = _skills_to_vec(req.skills, vocab)
        scores = _cosine_scores(u, M)
        if scores.size == 0:
            return []
        # сортировка: по score (cosine) ↓, тай-брейк — по популярности ↓
        order = np.lexsort((-pop, -scores))
        k = max(1, int(req.limit or 50))
        idx = order[:k]
        return [RecoResponseItem(id=int(ids[i]), score=float(scores[i])) for i in idx]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

# ================================
# Main
# ================================
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8100"))
    uvicorn.run("ml.server:app", host=host, port=port)
