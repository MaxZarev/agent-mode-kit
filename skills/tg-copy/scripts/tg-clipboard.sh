#!/usr/bin/env bash
# Copy a Telegram-ready formatted post to the macOS clipboard.
#
# Usage: tg-clipboard.sh <post.html> [post.txt]
#   post.html — HTML fragment with Telegram-supported inline tags
#               (<b>, <i>, <u>, <s>, <code>, <a href>, <br>)
#   post.txt  — optional plain-text fallback; generated from the HTML
#               via textutil when omitted
#
# Puts three flavors on the clipboard at once (it is still ONE paste):
#   public.html  — read by Telegram Desktop (Qt) on Cmd+V
#   public.rtf   — read by native Telegram for macOS on Cmd+V
#   plain text   — fallback for everything else (prevents the
#                  "hieroglyphs" effect of a rich-only clipboard)
set -euo pipefail

HTML_FILE="${1:?usage: tg-clipboard.sh <post.html> [post.txt]}"
TXT_FILE="${2:-}"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# -inputencoding is mandatory: the HTML fragment has no <meta charset>,
# and without it textutil guesses a legacy encoding, producing mojibake
RTF_FILE="$WORK_DIR/post.rtf"
textutil -stdin -inputencoding UTF-8 -format html -convert rtf -output "$RTF_FILE" < "$HTML_FILE"

if [[ -z "$TXT_FILE" ]]; then
    TXT_FILE="$WORK_DIR/post.txt"
    textutil -stdin -inputencoding UTF-8 -format html -convert txt \
        -encoding UTF-8 -output "$TXT_FILE" < "$HTML_FILE"
fi

osascript - "$HTML_FILE" "$RTF_FILE" "$TXT_FILE" <<'APPLESCRIPT'
on run argv
    set htmlData to read (POSIX file (item 1 of argv)) as «class HTML»
    set rtfData to read (POSIX file (item 2 of argv)) as «class RTF »
    set txtData to read (POSIX file (item 3 of argv)) as «class utf8»
    set the clipboard to {«class HTML»:htmlData, «class RTF »:rtfData, Unicode text:txtData}
end run
APPLESCRIPT

osascript -e 'clipboard info' | grep -q 'class HTML' || {
    echo "FAIL: clipboard is missing the HTML flavor" >&2
    exit 1
}
echo "OK: clipboard set (html $(wc -c < "$HTML_FILE" | tr -d ' ') B, rtf $(wc -c < "$RTF_FILE" | tr -d ' ') B)"
echo "--- plain-text preview:"
pbpaste | head -5
