---
name: gsheets
description: "Work with Google Sheets via gws CLI — create, read, write, update spreadsheets. Use this skill when the user wants to do something with a Google Sheet: create a spreadsheet, fill in data, read contents, update cells, add rows, format. Trigger when the user says 'create a spreadsheet', 'fill the spreadsheet', 'write to google sheet', 'read from spreadsheet', 'add a row', mentions a spreadsheet ID or Google Sheets link, or asks to structure data in tabular format in Google Sheets."
allowed-tools: Bash, Read, Write
---

Work with Google Sheets via `gws` CLI (Google Workspace CLI,
[`@googleworkspace/cli`](https://github.com/googleworkspace/cli) on npm).

## One-time setup

```bash
npm install -g @googleworkspace/cli
gws auth setup --login   # configures a GCP project + OAuth client (needs gcloud), then opens browser
# or, if you already have an OAuth client configured:
gws auth login -s sheets
```

Check state with `gws auth status`.

## Important: JSON escaping

`gws` incorrectly parses JSON passed directly via arguments in zsh.
Always wrap commands via heredoc:

```bash
cat <<'EOFCMD' | bash
gws sheets spreadsheets values update \
  --params '{"spreadsheetId":"ID","range":"Sheet1!A1:B2","valueInputOption":"USER_ENTERED"}' \
  --json '{"values":[["a","b"],["c","d"]]}'
EOFCMD
```

## Extracting spreadsheetId from a link

From URL `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit` take the part between `/d/` and `/edit`.

## Main operations

### Create a spreadsheet

```bash
cat <<'EOFCMD' | bash
gws sheets spreadsheets create --json '{"properties":{"title":"Spreadsheet Name"}}'
EOFCMD
```

Returns JSON with `spreadsheetId` and `spreadsheetUrl`.

### Read data

```bash
cat <<'EOFCMD' | bash
gws sheets +read --spreadsheet "SPREADSHEET_ID" --range "Sheet1!A1:Z100"
EOFCMD
```

For tabular output add `--format table`.

### Write / update data

```bash
cat <<'EOFCMD' | bash
gws sheets spreadsheets values update \
  --params '{"spreadsheetId":"ID","range":"Sheet1!A1:C3","valueInputOption":"USER_ENTERED"}' \
  --json '{"values":[["Header1","Header2","Header3"],["value1","value2","value3"]]}'
EOFCMD
```

`valueInputOption`:
- `USER_ENTERED` — parses values as user input (formulas, numbers, dates)
- `RAW` — writes as strings without parsing

### Append rows (SAFE method)

**IMPORTANT:** Always use `values append` API with a sheet name — Google automatically finds the last row and appends below. This prevents overwriting existing data.

**NEVER** use `values update` to add rows — it overwrites data at the specified range. `values update` is only acceptable for updating specific known cells.

```bash
cat <<'EOFCMD' | bash
gws sheets spreadsheets values append \
  --params '{"spreadsheetId":"ID","range":"SheetName!A:E","valueInputOption":"USER_ENTERED","insertDataOption":"INSERT_ROWS"}' \
  --json '{"values":[["value1","value2","value3"]]}'
EOFCMD
```

`+append` shortcut (only if the spreadsheet has one sheet — it does not support sheet selection):

```bash
cat <<'EOFCMD' | bash
gws sheets +append --spreadsheet "ID" --values 'value1,value2,value3'
EOFCMD
```

### Clear a range

```bash
cat <<'EOFCMD' | bash
gws sheets spreadsheets values clear \
  --params '{"spreadsheetId":"ID","range":"Sheet1!A1:Z100"}'
EOFCMD
```

### Batch update (formatting, merging cells, sheets)

Via `batchUpdate` you can: add/delete sheets, merge cells, change formatting, auto-resize columns, etc.

```bash
cat <<'EOFCMD' | bash
gws sheets spreadsheets batchUpdate \
  --params '{"spreadsheetId":"ID"}' \
  --json '{"requests":[{"addSheet":{"properties":{"title":"New Sheet"}}}]}'
EOFCMD
```

Example requests:
- `addSheet` — add a sheet
- `deleteSheet` — delete a sheet (requires `sheetId`)
- `mergeCells` — merge cells
- `repeatCell` — apply formatting to a range
- `autoResizeDimensions` — auto-resize columns
- `updateSheetProperties` — rename a sheet

### Get spreadsheet metadata

```bash
cat <<'EOFCMD' | bash
gws sheets spreadsheets get --params '{"spreadsheetId":"ID"}'
EOFCMD
```

## Strategy for filling large spreadsheets

For spreadsheets with large amounts of data:
1. First create the spreadsheet or get the ID of an existing one
2. Write headers via `values update` to the first row
3. Fill data in blocks via `values update` with correct ranges
4. Apply formatting via `batchUpdate` if needed

## Output to user

After creating a spreadsheet, always show the `spreadsheetUrl` link.
After writing, show how many cells were updated.
