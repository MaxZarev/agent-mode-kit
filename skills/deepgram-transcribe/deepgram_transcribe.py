#!/usr/bin/env python3
"""
Deepgram Transcriber — транскрибация аудио/видео с поддержкой всех форматов вывода.

Использование:
  python deepgram_transcribe.py audio.mp3
  python deepgram_transcribe.py meeting.mp4 --diarize
  python deepgram_transcribe.py *.mp3 --format srt --output-dir ./results
  python deepgram_transcribe.py audio.mp3 --all-formats
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel

load_dotenv()

console = Console()

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts", ".flv", ".wmv", ".3gp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".opus", ".wma", ".aiff"}

ALL_FORMATS = ["txt", "txt-speaker", "txt-time", "txt-full", "srt", "vtt", "md", "json"]


# ─── Вспомогательные функции ────────────────────────────────────────────────

def format_timestamp_srt(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_short_time(seconds: float) -> str:
    s = int(seconds) % 60
    m = int(seconds // 60)
    return f"[{m:02d}:{s:02d}]"


def speaker_name(speaker_id: int) -> str:
    return f"Спикер {speaker_id + 1}"


def extract_audio(video_path: Path) -> Path:
    """Извлечь аудио из видео через ffmpeg → временный WAV 16kHz mono."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out_path = Path(tmp.name)

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(out_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        console.print(f"[red]Ошибка ffmpeg:[/red]\n{result.stderr}")
        sys.exit(1)
    return out_path


# ─── Транскрибация ───────────────────────────────────────────────────────────

def transcribe_file(file_path: Path, args) -> object:
    from deepgram import DeepgramClient

    api_key = args.api_key or os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        console.print("[red]Ошибка:[/red] API ключ не найден.")
        console.print("Установите [bold]DEEPGRAM_API_KEY[/bold] в .env или используйте [bold]--api-key[/bold].")
        sys.exit(1)

    tmp_audio = None
    audio_path = file_path

    ext = file_path.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        console.print(f"  [dim]Извлечение аудио из видео...[/dim]")
        tmp_audio = extract_audio(file_path)
        audio_path = tmp_audio

    try:
        client = DeepgramClient(api_key=api_key)

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        kwargs = dict(
            request=audio_data,
            model=args.model,
            language=args.language,
            punctuate=True,
            smart_format=True,
            utterances=True,
            utt_split=2.0,
            diarize=args.diarize or args.all_formats,
        )

        if args.keyterms:
            kwargs["keyterm"] = [k.strip() for k in args.keyterms.split(",")]

        return client.listen.v1.media.transcribe_file(**kwargs)

    finally:
        if tmp_audio:
            tmp_audio.unlink(missing_ok=True)


# ─── Получение сегментов ─────────────────────────────────────────────────────

def words_to_segments(words):
    """Сгруппировать слова в сегменты по паузам и смене спикера."""
    if not words:
        return []
    segments = []
    current = [words[0]]
    current_spk = getattr(words[0], "speaker", 0) or 0

    for w in words[1:]:
        spk = getattr(w, "speaker", 0) or 0
        gap = w.start - current[-1].end
        if gap > 0.5 or spk != current_spk:
            segments.append({"words": current, "speaker": current_spk})
            current = [w]
            current_spk = spk
        else:
            current.append(w)
    segments.append({"words": current, "speaker": current_spk})

    return [
        {
            "start": g["words"][0].start,
            "end":   g["words"][-1].end,
            "text":  " ".join((w.punctuated_word or w.word) for w in g["words"]).strip(),
            "speaker": g["speaker"],
        }
        for g in segments
    ]


def get_segments(response):
    """Получить сегменты речи из ответа."""
    # Сначала пробуем utterances (есть при utterances=True)
    if response.results.utterances:
        return [
            {
                "start":   u.start,
                "end":     u.end,
                "text":    u.transcript.strip(),
                "speaker": getattr(u, "speaker", 0) or 0,
            }
            for u in response.results.utterances
        ]
    # Fallback: группируем слова
    words = list(response.results.channels[0].alternatives[0].words or [])
    return words_to_segments(words)


# ─── Форматтеры ─────────────────────────────────────────────────────────────

def fmt_txt(response) -> str:
    return response.results.channels[0].alternatives[0].transcript.strip()


def merge_by_speaker(segments):
    """Склеить соседние сегменты одного спикера в один блок."""
    if not segments:
        return []
    merged = [dict(segments[0])]
    for s in segments[1:]:
        if s["speaker"] == merged[-1]["speaker"]:
            merged[-1]["text"] += " " + s["text"]
            merged[-1]["end"] = s["end"]
        else:
            merged.append(dict(s))
    return merged


def fmt_txt_speaker(response) -> str:
    segments = merge_by_speaker(get_segments(response))
    return "\n".join(
        f"{speaker_name(s['speaker'])}: {s['text']}"
        for s in segments
    )


def fmt_txt_time(response) -> str:
    segments = get_segments(response)
    return "\n".join(
        f"{format_short_time(s['start'])} {s['text']}"
        for s in segments
    )


def fmt_txt_full(response) -> str:
    segments = merge_by_speaker(get_segments(response))
    return "\n".join(
        f"{format_short_time(s['start'])} {speaker_name(s['speaker'])}: {s['text']}"
        for s in segments
    )


def fmt_srt(response) -> str:
    blocks = []
    for i, s in enumerate(get_segments(response), 1):
        blocks.append(
            f"{i}\n{format_timestamp_srt(s['start'])} --> {format_timestamp_srt(s['end'])}\n{s['text']}"
        )
    return "\n\n".join(blocks)


def fmt_vtt(response) -> str:
    blocks = ["WEBVTT\n"]
    for i, s in enumerate(get_segments(response), 1):
        blocks.append(
            f"{i}\n{format_timestamp_vtt(s['start'])} --> {format_timestamp_vtt(s['end'])}\n{s['text']}"
        )
    return "\n\n".join(blocks)


def fmt_md(response, source_name: str = "") -> str:
    meta = response.metadata
    duration_s = int(meta.duration)
    segments = get_segments(response)
    speakers = {s["speaker"] for s in segments}
    models = ", ".join(meta.models or [])

    lines = [
        f"# Транскрипция: {source_name}",
        "",
        f"**Длительность:** {duration_s // 60}:{duration_s % 60:02d} | **Спикеров:** {len(speakers)} | **Модель:** {models}",
        "",
        "---",
        "",
    ]
    for s in segments:
        lines.append(f"**{format_short_time(s['start'])} {speaker_name(s['speaker'])}**")
        lines.append(s["text"])
        lines.append("")
    return "\n".join(lines)


def fmt_json(response) -> str:
    try:
        return response.model_dump_json(indent=2)
    except Exception:
        return json.dumps(response.dict(), indent=2, ensure_ascii=False)


FORMATTERS = {
    "txt":         (fmt_txt,         ".txt",  ""),
    "txt-speaker": (fmt_txt_speaker, ".txt",  "_speaker"),
    "txt-time":    (fmt_txt_time,    ".txt",  "_time"),
    "txt-full":    (fmt_txt_full,    ".txt",  "_full"),
    "srt":         (fmt_srt,         ".srt",  ""),
    "vtt":         (fmt_vtt,         ".vtt",  ""),
    "md":          (fmt_md,          ".md",   ""),
    "json":        (fmt_json,        ".json", ""),
}


# ─── Сохранение ──────────────────────────────────────────────────────────────

def save_or_print(content: str, fmt: str, source: Path, args):
    multi = args.all_formats or len(args.format) > 1 or len(args.files_resolved) > 1

    if multi or args.output_dir:
        out_dir = Path(args.output_dir) if args.output_dir else source.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        _, ext, suffix = FORMATTERS[fmt]
        out_path = out_dir / f"{source.stem}{suffix}{ext}"
        out_path.write_text(content, encoding="utf-8")
        console.print(f"  [green]✓[/green] {fmt:<12} → {out_path}")
    elif args.output:
        out_path = Path(args.output)
        out_path.write_text(content, encoding="utf-8")
        console.print(f"  [green]✓[/green] Сохранено: {out_path}")
    else:
        console.print()
        console.print(content)


def process_file(file_path: Path, args):
    file_path = Path(file_path)
    if not file_path.exists():
        console.print(f"[red]Файл не найден:[/red] {file_path}")
        return

    ext = file_path.suffix.lower()
    if ext not in VIDEO_EXTENSIONS and ext not in AUDIO_EXTENSIONS:
        console.print(f"[yellow]Неизвестный формат:[/yellow] {file_path} — пропускаю")
        return

    size_mb = file_path.stat().st_size / (1024 * 1024)
    console.print(f"\n[bold]{file_path.name}[/bold] [dim]({size_mb:.1f} MB)[/dim]")

    with Progress(
        SpinnerColumn(),
        TextColumn("  [progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Транскрибация...", total=None)
        response = transcribe_file(file_path, args)
        progress.update(task, description="Готово")

    formats_to_use = ALL_FORMATS if args.all_formats else args.format

    for fmt in formats_to_use:
        fn, _, _ = FORMATTERS[fmt]
        try:
            content = fn(response, source_name=file_path.name) if fmt == "md" else fn(response)
            save_or_print(content, fmt, file_path, args)
        except Exception as e:
            console.print(f"  [red]✗[/red] {fmt}: {e}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        description="Deepgram Transcriber — транскрибация аудио/видео",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Форматы вывода (--format):
  txt          Сплошной текст
  txt-speaker  Текст с именами спикеров
  txt-time     Текст с таймингами [MM:SS]
  txt-full     Таймингии + спикеры
  srt          Субтитры SRT
  vtt          WebVTT субтитры
  md           Markdown с метаданными
  json         Сырой JSON ответ Deepgram

Примеры:
  python deepgram_transcribe.py audio.mp3
  python deepgram_transcribe.py meeting.mp4 --diarize --format txt-full
  python deepgram_transcribe.py *.mp3 --all-formats --output-dir ./results
  python deepgram_transcribe.py audio.mp3 --format srt vtt --output-dir .
  python deepgram_transcribe.py audio.mp3 --language multi
        """
    )

    parser.add_argument("files", nargs="+", help="Аудио/видео файлы (поддерживаются маски *.mp3)")
    parser.add_argument("--format", "-f", nargs="+", choices=ALL_FORMATS, default=["txt"],
                        metavar="FORMAT", help=f"Форматы: {', '.join(ALL_FORMATS)}")
    parser.add_argument("--all-formats", "-A", action="store_true",
                        help="Сохранить во всех форматах сразу")
    parser.add_argument("--diarize", "-d", action="store_true",
                        help="Разделение на спикеров")
    parser.add_argument("--language", "-l", default="ru",
                        help="Язык: ru, en, multi и др. [по умолчанию: ru]")
    parser.add_argument("--model", "-m", default="nova-3",
                        help="Модель Deepgram [по умолчанию: nova-3]")
    parser.add_argument("--output", "-o",
                        help="Путь сохранения (для одного файла и одного формата)")
    parser.add_argument("--output-dir",
                        help="Директория для сохранения результатов")
    parser.add_argument("--keyterms", "-k",
                        help="Ключевые термины через запятую")
    parser.add_argument("--api-key",
                        help="Deepgram API ключ (или DEEPGRAM_API_KEY в .env)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]Deepgram Transcriber[/bold cyan]",
        subtitle=f"модель: {args.model} | язык: {args.language}"
    ))

    files = []
    for pattern in args.files:
        expanded = glob.glob(pattern)
        files.extend(expanded if expanded else [pattern])

    if not files:
        console.print("[red]Файлы не найдены.[/red]")
        sys.exit(1)

    args.files_resolved = files

    for f in files:
        process_file(Path(f), args)

    console.print("\n[bold green]Готово.[/bold green]")


if __name__ == "__main__":
    main()
