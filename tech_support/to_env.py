# save_env.py
import os
from pathlib import Path

ENV_KEYS = [
    "GIGACHAT_CLIENT_ID",
    "GIGACHAT_CLIENT_SECRET",
    "GIGACHAT_SCOPE",
    "GIGACHAT_MODEL",
    "GIGACHAT_TOKEN_URL",
    "GIGACHAT_CHAT_URL",
    "REQUEST_TIMEOUT_SECONDS",
    "RETRIES",
    "INSECURE_SSL",
    "GIGACHAT_CA_PATH",
]

DEFAULTS = {
    "GIGACHAT_SCOPE": "GIGACHAT_API_PERS",
    "GIGACHAT_MODEL": "GigaChat",
    "GIGACHAT_TOKEN_URL": "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
    "GIGACHAT_CHAT_URL": "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
    "REQUEST_TIMEOUT_SECONDS": "45",
    "RETRIES": "2",
    "INSECURE_SSL": "0",
    "GIGACHAT_CA_PATH": "",
}

def quote(v: str) -> str:
    # уберём пробелы краёв и экранируем #, = и пробелы
    v = (v or "").strip()
    if any(ch in v for ch in [' ', '#', '=', '"', "'"]):
        return '"' + v.replace('"', '\\"') + '"'
    return v

def main():
    dst = Path(".env")
    lines = []
    for key in ENV_KEYS:
        val = os.getenv(key, DEFAULTS.get(key, ""))
        if not val:
            # плейсхолдеры для ключей, которые нужно заполнить руками
            if key in ("GIGACHAT_CLIENT_ID", "GIGACHAT_CLIENT_SECRET"):
                val = f"<PUT_{key}_HERE>"
        lines.append(f"{key}={quote(val)}")
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {dst.resolve()}")

if __name__ == "__main__":
    main()
