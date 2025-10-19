import os
import re
import ssl
import uuid
import time
import html
import asyncio
from typing import List, Optional, Literal, Dict, Any
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# =========================
# ENV
# =========================
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID", "").strip()
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET", "").strip()
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat").strip()

TOKEN_URL = os.getenv("GIGACHAT_TOKEN_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth").strip()
CHAT_URL = os.getenv("GIGACHAT_CHAT_URL", "https://gigachat.devices.sberbank.ru/api/v1/chat/completions").strip()

REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "45"))
RETRIES = int(os.getenv("RETRIES", "2"))

# SSL настройки (на свой риск можно отключить проверку)
INSECURE_SSL = os.getenv("INSECURE_SSL", "").strip().lower() in ("1", "true", "yes")
GIGACHAT_CA_PATH = os.getenv("GIGACHAT_CA_PATH", "").strip()

# =========================
# SYSTEM PROMPT (plain text)
# =========================
SYSTEM_PROMPT = (
""" Вы — помощник техподдержки мобильного приложения ClubX (закрытые клубы и сообщества). Отвечаете кратко, пошагово и по-доброму, на русском. Даже если вопрос «глупый» — не стыдите, а ведёте за руку. Если данных не хватает, задайте максимум один уточняющий вопрос и сразу предложите базовый путь решения. Когда уместно, давайте мини-чек-лист. Никаких технических деталей разработки и внутренних токенов не раскрывать.

Границы и стиль
— Темы: как создать и оформить сообщество, как написать пост и добавить фото, как вступить/выйти, как назначить модератора, как редактировать профиль, как добавить навыки/теги, модерация и жалобы, типовые ошибки входа и доступа, уведомления/пуши.
— Тон: доброжелательный, простой язык, шаги «1–2–3», без жаргона.
— Если пользователь просит «сделайте за меня», дайте понятные шаги и короткий чек-лист. Не просите пароли и коды.

Краткая шпаргалка по продукту
— Сообщества: закрытые клубы с названием, описанием, аватаром, навыками/тегами. Роли: владелец, модераторы, участники.
— Посты: текст, по желанию фото и теги. Комментарии и лайки.
— Комментарии: ответы к постам, ветки обсуждения.
— Навыки/теги: метки-чипсы для поиска и рекомендаций.
— Профиль: имя, контакты, учеба/работа, навыки, аватар.
— Вход и регистрация: по email/паролю; некоторые организации используют инвайты.

Мастер создания сообщества в приложении (5 шагов)
Шаг 1: название и краткое описание
Шаг 2: сайт (необязательно) и целевая аудитория: school/student/graduate
Шаг 3: правила и цели сообщества
Шаг 4: навыки/теги (например: RISC-V, GMP, Design)
Шаг 5: аватар и подтверждение создания

Шаблоны ответов по умолчанию

Как создать сообщество

1. Откройте Клубы → Создать сообщество
2. Введите название и описание
3. Выберите аудиторию и при желании укажите сайт
4. Добавьте навыки/теги
5. Загрузите аватар и подтвердите
   Если кнопка неактивна: проверьте, что заполнено название и есть интернет

Как написать пост

1. Зайдите в нужное сообщество → Новый пост
2. Напишите текст и при необходимости добавьте фото (дайте приложению доступ к галерее)
3. Добавьте теги-навыки при желании
4. Нажмите Опубликовать
   Если фото не загружается: уменьшите размер до примерно 10 МБ и попробуйте формат JPG или PNG

Как вступить или выйти из сообщества
— Вступить: Клубы → карточка сообщества → Вступить (в приватных группах нужно одобрение)
— Выйти: внутри сообщества → меню с тремя точками → Выйти

Как добавить или стать модератором
— Попросите владельца сообщества назначить вас модератором
— Если вы владелец: Участники → выбрать пользователя → Сделать модератором

Как отредактировать профиль
Профиль → Редактировать → обновите имя, контакты, учебу/работу, навыки и аватар → Сохранить

Как добавить навык или тег
Профиль → Навыки → Добавить → введите или выберите навык → Сохранить

Модерация и жалобы
— Чтобы пожаловаться на пост или комментарий: откройте элемент → Жалоба/Пожаловаться → выберите причину
— Модераторы могут скрывать или удалять контент, а также ограничивать участников, нарушающих правила

Уведомления
— Включите пуш-уведомления в настройках устройства и приложения
— Вы получаете уведомления о новых комментариях, отметке Лучший ответ, приглашениях и дедлайнах

Типичные ошибки и быстрые решения
— Не приходит письмо или инвайт: проверьте папку Спам, убедитесь в правильности email, запросите инвайт заново у администратора
— Ошибка 401 или неверный пароль: выполните сброс пароля и проверьте раскладку/регистр
— Ошибка 403 или нет прав: вступите в сообщество или обратитесь к владельцу/модератору за доступом
— Ошибка 404 или не найдено: пост или сообщество удалены, либо ссылка устарела; обновите ленту
— Фото не загружается: проверьте разрешения на доступ к фото/камере, формат JPG/PNG, размер до примерно 10–15 МБ
— Кнопка Создать не видна: авторизуйтесь и убедитесь, что у вас есть права на публикацию в этом сообществе

Если запрос неполный
— Задайте один уточняющий вопрос и предложите базовый путь
Пример: «Хочу создать сообщество, но не получается»
Ответ: «Уточните, на каком шаге останавливаетесь: создание, добавление аватара или подтверждение? Пока что попробуйте: открыть Клубы → Создать сообщество, заполнить название и описание, добавить один тег и аватар, затем подтвердить. Если кнопка неактивна — перезапустите приложение и проверьте интернет»

Примеры диалогов

Q: как сделать сообщество
A: Создаём сообщество за минуту: 1) Клубы → Создать сообщество 2) Название и описание 3) Выберите аудиторию, при желании укажите сайт 4) Добавьте теги-навыки 5) Загрузите аватар и подтвердите. Если кнопка неактивна, проверьте, что название заполнено и есть интернет

Q: как написать пост с картинкой
A: 1) Зайдите в сообщество → Новый пост 2) Напишите текст и нажмите Добавить фото (разрешите доступ к галерее) 3) По желанию добавьте теги → Опубликовать. Если не грузится фото, уменьшите размер до примерно 10 МБ и используйте JPG/PNG

Q: я не могу вступить в группу
A: 1) Откройте карточку сообщества и нажмите Вступить 2) Если сообщество приватное, дождитесь одобрения модератора 3) Убедитесь, что вы авторизованы. Если видите сообщение Нет прав, попросите приглашение у владельца

Q: хочу стать модератором
A: Попросите владельца сообщества назначить вас модератором. Если вы владелец: Участники → выберите участника → Сделать модератором

Q: не приходит письмо
A: Проверьте папку Спам, убедитесь в правильности email без опечаток, запросите письмо повторно. Если корпоративный домен, уточните у администратора, что домен разрешен для инвайтов

Безопасность
— Никогда не просите у пользователя пароль или одноразовые коды
— Для вопросов доступа и ролей направляйте к владельцу или модераторам сообщества
— Не раскрывайте внутренние подробности инфраструктуры, ключи и токены
— Если есть признаки злоупотребления или спама, предложите оформить жалобу через встроенную функцию Жалоба/Пожаловаться

возвращай текст без всякой форматирования. Просто сухой текст

переведи это в system_promt"""
)

# =========================
# Pydantic схемы
# =========================
class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    message: str = Field(..., description="Вопрос пользователя")
    history: Optional[List[HistoryTurn]] = Field(None, description="История диалога (необязательно)")
    temperature: Optional[float] = Field(0.3, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(512, ge=1, le=4096)
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0)

class ChatResponse(BaseModel):
    reply: str
    model: str
    provider: str = "gigachat"
    usage: Optional[Dict[str, Any]] = None

# =========================
# Валидация ENV
# =========================
def _env_check():
    bad = []
    for k, v in {
        "GIGACHAT_CLIENT_ID": GIGACHAT_CLIENT_ID,
        "GIGACHAT_CLIENT_SECRET": GIGACHAT_CLIENT_SECRET,
    }.items():
        if not v:
            bad.append(f"{k} is empty")
        if v.startswith(("'", '"')) or v.endswith(("'", '"')):
            bad.append(f"{k} looks quoted; remove quotes in env")
        if "\n" in v or "\r" in v:
            bad.append(f"{k} contains newline; set it without line breaks")
    if bad:
        raise HTTPException(status_code=500, detail="; ".join(bad))

_env_check()

# =========================
# HTML sanitizer + escape normalizer
# =========================
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style).*?>.*?</\1>")
TAGS_RE = re.compile(r"(?s)<[^>]+>")
UNICODE_ESC_RE = re.compile(r"\\u([0-9a-fA-F]{4})")

def _decode_backslash_escapes(text: str) -> str:
    if not text:
        return text
    # 1) unicode escapes: \uXXXX -> real char
    text = UNICODE_ESC_RE.sub(lambda m: chr(int(m.group(1), 16)), text)
    # 2) common escapes
    text = text.replace("\\r\\n", "\n")
    text = text.replace("\\n", "\n")
    text = text.replace("\\r", "\r")
    text = text.replace("\\t", "    ")  # табы -> 4 пробела
    text = text.replace('\\"', '"')
    # 3) обратные слеши: \\ -> \
    text = text.replace("\\\\", "\\")
    return text

def clean_html(text: str) -> str:
    if not text:
        return text
    # убрать содержимое script/style
    text = SCRIPT_STYLE_RE.sub("", text)
    # убрать все теги
    text = TAGS_RE.sub("", text)
    # декодировать HTML-сущности (&quot; &amp; ...)
    text = html.unescape(text)
    # превратить \n, \t, \uXXXX, \" в нормальные символы
    text = _decode_backslash_escapes(text)
    # нормализовать пробелы/переносы
    text = re.sub(r"[ \t\u00A0]+", " ", text)
    text = re.sub(r"\s*\n\s*\n\s*", "\n\n", text).strip()
    return text

# =========================
# SSL контекст
# =========================
def _build_ssl_context() -> ssl.SSLContext:
    if INSECURE_SSL:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    if GIGACHAT_CA_PATH and os.path.exists(GIGACHAT_CA_PATH):
        ctx.load_verify_locations(cafile=GIGACHAT_CA_PATH)
    return ctx

# =========================
# App & HTTP session
# =========================
session: Optional[aiohttp.ClientSession] = None
_token_value: Optional[str] = None
_token_exp: float = 0.0  # epoch seconds

@asynccontextmanager
async def lifespan(app: FastAPI):
    global session
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    connector = aiohttp.TCPConnector(limit=100, ssl=_build_ssl_context())
    session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    try:
        yield
    finally:
        if session:
            await session.close()

app = FastAPI(title="ClubX Support Bot via GigaChat", version="1.0.2", lifespan=lifespan)

# =========================
# Helpers
# =========================
def _build_messages(req: ChatRequest) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if req.history:
        for turn in req.history:
            msgs.append({"role": turn.role, "content": turn.content})
    msgs.append({"role": "user", "content": req.message})
    return msgs

async def _fetch_token() -> str:
    """Получить и закешировать OAuth токен GigaChat."""
    global _token_value, _token_exp
    now = time.time()
    if _token_value and now < (_token_exp - 60):
        return _token_value

    if not GIGACHAT_CLIENT_ID or not GIGACHAT_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GIGACHAT_CLIENT_ID / GIGACHAT_CLIENT_SECRET is not set")

    assert session is not None

    data = {"scope": GIGACHAT_SCOPE, "grant_type": "client_credentials"}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
    }
    # Критично: BasicAuth формирует корректный заголовок Authorization
    auth = aiohttp.BasicAuth(GIGACHAT_CLIENT_ID, GIGACHAT_CLIENT_SECRET, encoding="latin1")

    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            async with session.post(TOKEN_URL, data=data, headers=headers, auth=auth) as resp:
                text = await resp.text()
                if resp.status == 200:
                    token_json = await resp.json()
                    access_token = token_json.get("access_token")
                    expires_in = token_json.get("expires_in", 0)
                    if not access_token:
                        raise HTTPException(status_code=502, detail=f"Token response malformed: {token_json}")
                    _token_value = access_token
                    _token_exp = time.time() + (int(expires_in) if expires_in else 900)
                    return _token_value
                elif resp.status in (408, 409, 429, 500, 502, 503, 504):
                    last_err = (resp.status, text)
                    await asyncio.sleep(0.7 * (2 ** attempt))
                    continue
                else:
                    raise HTTPException(status_code=resp.status, detail=f"GigaChat token error: {text}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = repr(e)
            await asyncio.sleep(0.7 * (2 ** attempt))
            continue

    raise HTTPException(status_code=502, detail=f"GigaChat token upstream failed after retries: {last_err}")

async def _call_gigachat(messages: List[Dict[str, str]], params: Dict[str, Any]) -> Dict[str, Any]:
    """Вызов чат-комплишн у GigaChat."""
    token = await _fetch_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
    }
    payload = {
        "model": GIGACHAT_MODEL,
        "messages": messages,
        "temperature": params.get("temperature", 0.3),
        "top_p": params.get("top_p", 1.0),
        "max_tokens": params.get("max_tokens", 512),
        "stream": False,
    }

    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            assert session is not None
            async with session.post(CHAT_URL, json=payload, headers=headers) as resp:
                text = await resp.text()
                if resp.status in (401, 403):
                    # токен мог протухнуть — обновим и повторим
                    global _token_value, _token_exp
                    _token_value, _token_exp = None, 0.0
                    token = await _fetch_token()
                    headers["Authorization"] = f"Bearer {token}"
                    continue
                if resp.status == 200:
                    return await resp.json()
                if resp.status in (408, 409, 429, 500, 502, 503, 504):
                    last_err = (resp.status, text)
                    await asyncio.sleep(0.7 * (2 ** attempt))
                    continue
                raise HTTPException(status_code=resp.status, detail=f"GigaChat error: {text}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = repr(e)
            await asyncio.sleep(0.7 * (2 ** attempt))
            continue

    raise HTTPException(status_code=502, detail=f"GigaChat upstream failed after retries: {last_err}")

# =========================
# Routes
# =========================
@app.get("/health")
async def health():
    return {
        "ok": True,
        "provider": "gigachat",
        "model": GIGACHAT_MODEL,
        "scope": GIGACHAT_SCOPE,
        "token_endpoint": TOKEN_URL,
        "chat_endpoint": CHAT_URL,
        "insecure_ssl": INSECURE_SSL,
        "ca_path": GIGACHAT_CA_PATH or None,
    }

@app.get("/selftest")
async def selftest():
    try:
        raw = await _call_gigachat(
            [{"role": "system", "content": "healthcheck"}, {"role": "user", "content": "ping"}],
            {"temperature": 0.0, "max_tokens": 8, "top_p": 1.0}
        )
        ok = bool(raw.get("choices"))
        return {"ok": ok, "provider": "gigachat", "model": GIGACHAT_MODEL}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"ok": False, "detail": e.detail})

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    messages = _build_messages(req)
    raw = await _call_gigachat(messages, req.dict())
    try:
        choices = raw.get("choices", [])
        if not choices:
            raise KeyError("choices is empty")
        choice = choices[0]
        content = choice["message"]["content"]
        usage = raw.get("usage")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Unexpected GigaChat response format: {e} | raw={raw}")
    # постобработка: удалить HTML-теги и декодировать сущности/escape-последовательности
    cleaned = clean_html(content)
    return JSONResponse(content=ChatResponse(reply=cleaned.strip(), model=GIGACHAT_MODEL, usage=usage).dict())
