#!/usr/bin/env python3
"""YouTube CLI — управление каналом через YouTube Data API v3."""

import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "youtube-cli"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
TOKEN_FILE = CONFIG_DIR / "token.json"
CHANNEL_FILE = CONFIG_DIR / "channel.txt"


def get_channel_id():
    if CHANNEL_FILE.exists():
        return CHANNEL_FILE.read_text().strip()
    return None


def require_channel_id():
    cid = get_channel_id()
    if not cid:
        print("Канал не задан. Выполни: youtube channel set UC...", file=sys.stderr)
        sys.exit(1)
    return cid

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtubepartner",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

CATEGORIES = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "19": "Travel & Events",
    "20": "Gaming", "22": "People & Blogs", "23": "Comedy",
    "24": "Entertainment", "25": "News & Politics", "26": "Howto & Style",
    "27": "Education", "28": "Science & Technology", "29": "Nonprofits & Activism",
}


def get_youtube():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN_FILE.exists():
        print("Ошибка: не авторизован. Запусти: youtube auth", file=sys.stderr)
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def get_youtube_analytics():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN_FILE.exists():
        print("Ошибка: не авторизован. Запусти: youtube auth", file=sys.stderr)
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return build("youtubeAnalytics", "v2", credentials=creds)


# ─── AUTH ──────────────────────────────────────────────────────────────────────

def cmd_auth(args):
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CREDENTIALS_FILE.exists():
        print(f"Ошибка: положи client_secret.json сюда:\n  {CREDENTIALS_FILE}")
        print("\nКак получить:")
        print("  1. console.cloud.google.com → новый проект")
        print("  2. APIs & Services → Enable APIs → YouTube Data API v3")
        print("  3. Credentials → Create → OAuth 2.0 Client ID → Desktop app")
        print("  4. Скачай JSON и переименуй в credentials.json")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Авторизация успешна. Токен сохранён: {TOKEN_FILE}")


# ─── UPLOAD ────────────────────────────────────────────────────────────────────

def cmd_upload(args):
    from googleapiclient.http import MediaFileUpload

    if not os.path.exists(args.file):
        print(f"Ошибка: файл не найден: {args.file}", file=sys.stderr)
        sys.exit(1)

    youtube = get_youtube()

    body = {
        "snippet": {
            "title": args.title or Path(args.file).stem,
            "description": args.description or "",
            "tags": [t.strip() for t in args.tags.split(",")] if args.tags else [],
            "categoryId": args.category,
        },
        "status": {
            "privacyStatus": args.privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    if args.schedule:
        body["status"]["publishAt"] = args.schedule
        body["status"]["privacyStatus"] = "private"

    media = MediaFileUpload(args.file, chunksize=10 * 1024 * 1024, resumable=True)

    print(f"Загружаю: {args.file}")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"\r  {pct}%", end="", flush=True)

    print(f"\nГотово! https://youtube.com/watch?v={response['id']}")
    if args.schedule:
        print(f"Запланировано: {args.schedule}")


# ─── UPDATE METADATA ───────────────────────────────────────────────────────────

def cmd_update(args):
    youtube = get_youtube()

    video = youtube.videos().list(part="snippet,status", id=args.id).execute()
    if not video["items"]:
        print(f"Видео не найдено: {args.id}", file=sys.stderr)
        sys.exit(1)

    item = video["items"][0]
    snippet = item["snippet"]
    status = item["status"]

    if args.title:       snippet["title"] = args.title
    if args.description: snippet["description"] = args.description
    if args.tags:        snippet["tags"] = [t.strip() for t in args.tags.split(",")]
    if args.category:    snippet["categoryId"] = args.category
    if args.privacy:     status["privacyStatus"] = args.privacy

    youtube.videos().update(
        part="snippet,status",
        body={"id": args.id, "snippet": snippet, "status": status}
    ).execute()

    print(f"Обновлено: https://youtube.com/watch?v={args.id}")


# ─── THUMBNAIL ─────────────────────────────────────────────────────────────────

def cmd_thumbnail(args):
    from googleapiclient.http import MediaFileUpload

    if not os.path.exists(args.image):
        print(f"Ошибка: файл не найден: {args.image}", file=sys.stderr)
        sys.exit(1)

    youtube = get_youtube()
    media = MediaFileUpload(args.image)
    youtube.thumbnails().set(videoId=args.id, media_body=media).execute()
    print(f"Превью установлено: https://youtube.com/watch?v={args.id}")


# ─── PRIVACY ───────────────────────────────────────────────────────────────────

def cmd_privacy(args):
    youtube = get_youtube()
    youtube.videos().update(
        part="status",
        body={"id": args.id, "status": {"privacyStatus": args.status}}
    ).execute()
    print(f"Приватность: {args.status} → https://youtube.com/watch?v={args.id}")


# ─── SCHEDULE ──────────────────────────────────────────────────────────────────

def cmd_schedule(args):
    youtube = get_youtube()
    youtube.videos().update(
        part="status",
        body={"id": args.id, "status": {
            "privacyStatus": "private",
            "publishAt": args.time,
        }}
    ).execute()
    print(f"Запланировано на {args.time}: https://youtube.com/watch?v={args.id}")


# ─── DELETE ────────────────────────────────────────────────────────────────────

def cmd_delete(args):
    confirm = input(f"Удалить видео {args.id}? [y/N] ")
    if confirm.lower() != "y":
        print("Отменено.")
        return

    get_youtube().videos().delete(id=args.id).execute()
    print(f"Удалено: {args.id}")


# ─── LIST VIDEOS ───────────────────────────────────────────────────────────────

def cmd_list(args):
    youtube = get_youtube()

    channel_id = get_channel_id()
    params = {"part": "contentDetails", "id": channel_id} if channel_id else {"part": "contentDetails", "mine": True}
    channel = youtube.channels().list(**params).execute()
    if not channel.get("items"):
        print("Канал не найден. Если у аккаунта только редакторский доступ — выполни: youtube channel set UC...")
        sys.exit(1)
    playlist_id = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    items = youtube.playlistItems().list(
        part="snippet",
        playlistId=playlist_id,
        maxResults=args.limit
    ).execute()

    for item in items["items"]:
        s = item["snippet"]
        vid = s["resourceId"]["videoId"]
        privacy = s.get("status", {}).get("privacyStatus", "—")
        print(f"{vid}  {s['publishedAt'][:10]}  [{privacy:10}]  {s['title']}")


# ─── PLAYLISTS ─────────────────────────────────────────────────────────────────

def cmd_playlist_list(args):
    youtube = get_youtube()
    result = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
    for item in result["items"]:
        print(f"{item['id']}  {item['snippet']['title']}")


def cmd_playlist_create(args):
    youtube = get_youtube()
    result = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": args.title, "description": args.description or ""},
            "status": {"privacyStatus": args.privacy},
        }
    ).execute()
    print(f"Создан плейлист: {result['id']}  {args.title}")


def cmd_playlist_add(args):
    youtube = get_youtube()
    youtube.playlistItems().insert(
        part="snippet",
        body={"snippet": {
            "playlistId": args.playlist,
            "resourceId": {"kind": "youtube#video", "videoId": args.video},
        }}
    ).execute()
    print(f"Видео {args.video} добавлено в плейлист {args.playlist}")


def cmd_playlist_remove(args):
    youtube = get_youtube()
    items = youtube.playlistItems().list(
        part="id",
        playlistId=args.playlist,
        videoId=args.video
    ).execute()
    if not items["items"]:
        print("Видео не найдено в этом плейлисте.")
        return
    youtube.playlistItems().delete(id=items["items"][0]["id"]).execute()
    print(f"Видео {args.video} удалено из плейлиста {args.playlist}")


# ─── COMMENTS ──────────────────────────────────────────────────────────────────

def cmd_comment_list(args):
    youtube = get_youtube()
    result = youtube.commentThreads().list(
        part="snippet",
        videoId=args.id,
        maxResults=args.limit,
        order="relevance"
    ).execute()

    for item in result["items"]:
        c = item["snippet"]["topLevelComment"]["snippet"]
        tid = item["id"]
        print(f"\n[{tid}] {c['authorDisplayName']} ({c['publishedAt'][:10]}):")
        print(f"  {c['textDisplay']}")


def cmd_comment_post(args):
    youtube = get_youtube()
    result = youtube.commentThreads().insert(
        part="snippet",
        body={"snippet": {
            "videoId": args.id,
            "topLevelComment": {"snippet": {"textOriginal": args.text}},
        }}
    ).execute()
    print(f"Комментарий опубликован: {result['id']}")


def cmd_comment_reply(args):
    youtube = get_youtube()
    result = youtube.comments().insert(
        part="snippet",
        body={"snippet": {
            "parentId": args.comment,
            "textOriginal": args.text,
        }}
    ).execute()
    print(f"Ответ опубликован: {result['id']}")


def cmd_comment_delete(args):
    get_youtube().comments().delete(id=args.id).execute()
    print(f"Комментарий удалён: {args.id}")


# ─── ANALYTICS ─────────────────────────────────────────────────────────────────

def cmd_analytics(args):
    youtube = get_youtube()
    analytics = get_youtube_analytics()

    channel = youtube.channels().list(part="id", mine=True).execute()
    channel_id = channel["items"][0]["id"]

    filters = f"video=={args.id}" if args.id else None

    params = dict(
        ids=f"channel=={channel_id}",
        startDate=args.start or "2020-01-01",
        endDate=args.end or "2099-12-31",
        metrics="views,estimatedMinutesWatched,averageViewDuration,likes,comments,subscribersGained",
        dimensions="day" if args.daily else None,
        filters=filters,
    )
    params = {k: v for k, v in params.items() if v is not None}

    result = analytics.reports().query(**params).execute()

    headers = [h["name"] for h in result["columnHeaders"]]
    print("  ".join(f"{h:>25}" for h in headers))
    print("─" * (27 * len(headers)))
    for row in result.get("rows", []):
        print("  ".join(f"{str(v):>25}" for v in row))


# ─── SEARCH ────────────────────────────────────────────────────────────────────

def cmd_search(args):
    youtube = get_youtube()
    result = youtube.search().list(
        part="snippet",
        q=args.query,
        type="video",
        maxResults=args.limit,
        order=args.order,
    ).execute()

    for item in result["items"]:
        vid = item["id"]["videoId"]
        s = item["snippet"]
        print(f"{vid}  {s['publishedAt'][:10]}  {s['channelTitle'][:20]:20}  {s['title']}")


# ─── TRENDING ──────────────────────────────────────────────────────────────────

def cmd_trending(args):
    youtube = get_youtube()
    result = youtube.videos().list(
        part="snippet,statistics",
        chart="mostPopular",
        regionCode=args.region,
        videoCategoryId=args.category or "",
        maxResults=args.limit,
    ).execute()

    for item in result["items"]:
        s = item["snippet"]
        st = item["statistics"]
        views = int(st.get("viewCount", 0))
        print(f"{item['id']}  {views:>10,}  {s['channelTitle'][:20]:20}  {s['title']}")


# ─── QUOTA ─────────────────────────────────────────────────────────────────────

def cmd_quota(args):
    print("YouTube Data API v3 квота:")
    print("  10 000 единиц/день бесплатно")
    print()
    print("Стоимость операций:")
    costs = [
        ("upload",          1600, "загрузка видео"),
        ("videos.list",        1, "список/поиск видео"),
        ("videos.update",     50, "обновление метаданных"),
        ("thumbnails.set",    50, "установка превью"),
        ("search.list",      100, "поиск"),
        ("commentThreads",    50, "комментарии"),
        ("analytics.query",    1, "аналитика"),
    ]
    for op, cost, desc in costs:
        print(f"  {op:25} {cost:>5}  ({desc})")
    print()
    print("Увеличить: console.cloud.google.com → APIs → YouTube Data API v3 → Quotas")


# ─── CATEGORIES ────────────────────────────────────────────────────────────────

def cmd_categories(args):
    youtube = get_youtube()
    result = youtube.videoCategories().list(part="snippet", regionCode=args.region).execute()
    for item in result["items"]:
        if item["snippet"].get("assignable"):
            print(f"  {item['id']:>4}  {item['snippet']['title']}")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    p = argparse.ArgumentParser(prog="youtube", description="YouTube CLI")
    sub = p.add_subparsers(dest="cmd", metavar="команда")

    # auth
    sub.add_parser("auth", help="OAuth2 авторизация")

    # upload
    pu = sub.add_parser("upload", help="Загрузить видео")
    pu.add_argument("file", help="Путь к видеофайлу")
    pu.add_argument("--title", "-t", help="Заголовок")
    pu.add_argument("--description", "-d", help="Описание")
    pu.add_argument("--tags", help="Теги через запятую")
    pu.add_argument("--category", default="22", help="ID категории (по умолчанию 22 = People & Blogs)")
    pu.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    pu.add_argument("--schedule", help="Отложенная публикация: 2026-03-10T15:00:00Z")

    # update
    pm = sub.add_parser("update", help="Обновить метаданные видео")
    pm.add_argument("id", help="Video ID")
    pm.add_argument("--title", "-t")
    pm.add_argument("--description", "-d")
    pm.add_argument("--tags")
    pm.add_argument("--category")
    pm.add_argument("--privacy", choices=["private", "unlisted", "public"])

    # thumbnail
    pt = sub.add_parser("thumbnail", help="Установить превью")
    pt.add_argument("id", help="Video ID")
    pt.add_argument("image", help="Путь к изображению (JPG/PNG)")

    # privacy
    pp = sub.add_parser("privacy", help="Изменить приватность")
    pp.add_argument("id", help="Video ID")
    pp.add_argument("status", choices=["private", "unlisted", "public"])

    # schedule
    ps = sub.add_parser("schedule", help="Запланировать публикацию")
    ps.add_argument("id", help="Video ID")
    ps.add_argument("time", help="Время публикации: 2026-03-10T15:00:00Z")

    # delete
    pd = sub.add_parser("delete", help="Удалить видео")
    pd.add_argument("id", help="Video ID")

    # list
    pl = sub.add_parser("list", help="Список своих видео")
    pl.add_argument("--limit", type=int, default=20)

    # playlist
    ppl = sub.add_parser("playlist", help="Управление плейлистами")
    ppl_sub = ppl.add_subparsers(dest="playlist_cmd", metavar="действие")

    ppl_sub.add_parser("list", help="Список плейлистов")

    pplc = ppl_sub.add_parser("create", help="Создать плейлист")
    pplc.add_argument("title")
    pplc.add_argument("--description", "-d", default="")
    pplc.add_argument("--privacy", default="public", choices=["private", "unlisted", "public"])

    ppla = ppl_sub.add_parser("add", help="Добавить видео в плейлист")
    ppla.add_argument("playlist", help="Playlist ID")
    ppla.add_argument("video", help="Video ID")

    pplr = ppl_sub.add_parser("remove", help="Удалить видео из плейлиста")
    pplr.add_argument("playlist", help="Playlist ID")
    pplr.add_argument("video", help="Video ID")

    # comment
    pco = sub.add_parser("comment", help="Комментарии")
    pco_sub = pco.add_subparsers(dest="comment_cmd", metavar="действие")

    pcol = pco_sub.add_parser("list", help="Список комментариев")
    pcol.add_argument("id", help="Video ID")
    pcol.add_argument("--limit", type=int, default=20)

    pcop = pco_sub.add_parser("post", help="Опубликовать комментарий")
    pcop.add_argument("id", help="Video ID")
    pcop.add_argument("text")

    pcor = pco_sub.add_parser("reply", help="Ответить на комментарий")
    pcor.add_argument("comment", help="Comment Thread ID")
    pcor.add_argument("text")

    pcod = pco_sub.add_parser("delete", help="Удалить комментарий")
    pcod.add_argument("id", help="Comment ID")

    # analytics
    pan = sub.add_parser("analytics", help="Аналитика")
    pan.add_argument("--id", help="Video ID (без — весь канал)")
    pan.add_argument("--start", help="Начало периода: 2026-01-01")
    pan.add_argument("--end", help="Конец периода: 2026-12-31")
    pan.add_argument("--daily", action="store_true", help="Разбивка по дням")

    # search
    pse = sub.add_parser("search", help="Поиск на YouTube")
    pse.add_argument("query")
    pse.add_argument("--limit", type=int, default=10)
    pse.add_argument("--order", default="relevance",
                     choices=["relevance", "date", "rating", "viewCount", "title"])

    # trending
    ptr = sub.add_parser("trending", help="Популярные видео")
    ptr.add_argument("--region", default="RU")
    ptr.add_argument("--category")
    ptr.add_argument("--limit", type=int, default=10)

    # channel
    pch = sub.add_parser("channel", help="Настройка канала")
    pch_sub = pch.add_subparsers(dest="channel_cmd")
    pch_set = pch_sub.add_parser("set", help="Задать channel ID")
    pch_set.add_argument("id", help="Channel ID (UC...)")
    pch_sub.add_parser("get", help="Показать текущий channel ID")

    # quota
    sub.add_parser("quota", help="Информация о квоте API")

    # categories
    pcat = sub.add_parser("categories", help="Список категорий")
    pcat.add_argument("--region", default="RU")

    args = p.parse_args()

    if not args.cmd:
        p.print_help()
        return

    dispatch = {
        "auth":       cmd_auth,
        "upload":     cmd_upload,
        "update":     cmd_update,
        "thumbnail":  cmd_thumbnail,
        "privacy":    cmd_privacy,
        "schedule":   cmd_schedule,
        "delete":     cmd_delete,
        "list":       cmd_list,
        "analytics":  cmd_analytics,
        "search":     cmd_search,
        "trending":   cmd_trending,
        "quota":      cmd_quota,
        "categories": cmd_categories,
    }

    if args.cmd == "playlist":
        if not args.playlist_cmd:
            cmd_playlist_list(args)
        else:
            {"list": cmd_playlist_list, "create": cmd_playlist_create,
             "add": cmd_playlist_add, "remove": cmd_playlist_remove}[args.playlist_cmd](args)
    elif args.cmd == "comment":
        if not args.comment_cmd:
            pco.print_help()
        else:
            {"list": cmd_comment_list, "post": cmd_comment_post,
             "reply": cmd_comment_reply, "delete": cmd_comment_delete}[args.comment_cmd](args)
    elif args.cmd == "channel":
        if args.channel_cmd == "set":
            CHANNEL_FILE.write_text(args.id)
            print(f"Channel ID сохранён: {args.id}")
        elif args.channel_cmd == "get":
            cid = get_channel_id()
            print(cid if cid else "Не задан. Выполни: youtube channel set UC...")
        else:
            pch.print_help()
    else:
        dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
