#!/usr/bin/env python3
"""Транскрипт YouTube-видео через Gemini API (видео обрабатывается на серверах Google).

Использование:
  python3 yt_transcript.py <youtube-url> [--out файл.md] [--mode transcript|summary]
                           [--model gemini-3.5-flash] [--prompt "свой промпт"]

Ключ: GEMINI_API_KEY в .env рядом со скриптом (см. .env.example).
Зависимостей нет — только стандартная библиотека.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPTS = {
    "transcript": (
        "Сделай максимально точный и полный транскрипт этого видео на языке оригинала. "
        "Передавай речь дословно, ничего не сокращай и не пересказывай. "
        "Каждые 30–60 секунд ставь таймкод в формате [MM:SS]. "
        "Если в кадре показывают важный текст (код, слайды, интерфейс) — вставляй его "
        "в квадратных скобках с пометкой [на экране: ...]. "
        "В начале укажи название видео и автора, если они видны."
    ),
    "summary": (
        "Составь подробный конспект этого видео на русском: основные тезисы по разделам "
        "с таймкодами [MM:SS], важные цифры и примеры, выводы автора."
    ),
}


def load_key(env_path: Path) -> str:
    if not env_path.exists():
        sys.exit(f"Нет файла {env_path} — создайте его из .env.example и заполните GEMINI_API_KEY")
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("GEMINI_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if key and "your-" not in key:
                return key
    sys.exit("GEMINI_API_KEY не заполнен в .env")


def main() -> None:
    ap = argparse.ArgumentParser(description="YouTube → транскрипт через Gemini")
    ap.add_argument("url", help="Ссылка на YouTube-видео (публичное)")
    ap.add_argument("--out", help="Куда сохранить результат (по умолчанию — stdout)")
    ap.add_argument("--mode", choices=list(PROMPTS), default="transcript")
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--prompt", help="Свой промпт вместо стандартного")
    args = ap.parse_args()

    key = load_key(Path(__file__).parent / ".env")

    body = {
        "contents": [{
            "parts": [
                {"file_data": {"file_uri": args.url}},
                {"text": args.prompt or PROMPTS[args.mode]},
            ],
        }],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 65536},
    }

    req = urllib.request.Request(
        API_URL.format(model=args.model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"Ошибка Gemini API (HTTP {e.code}): {detail[:2000]}")

    try:
        cand = data["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
    except (KeyError, IndexError):
        sys.exit(f"Неожиданный ответ API: {json.dumps(data, ensure_ascii=False)[:2000]}")

    if cand.get("finishReason") not in (None, "STOP"):
        print(f"ВНИМАНИЕ: генерация оборвана ({cand.get('finishReason')}) — "
              f"транскрипт может быть неполным", file=sys.stderr)

    if args.out:
        Path(args.out).write_text(text)
        print(f"Сохранено: {args.out} ({len(text)} символов)")
    else:
        print(text)


if __name__ == "__main__":
    main()
