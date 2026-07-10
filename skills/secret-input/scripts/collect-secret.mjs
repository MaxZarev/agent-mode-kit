#!/usr/bin/env node
// secret-input: collect env values (secrets or plain config) via a local
// one-shot web page, without the values ever passing through chat, terminal
// output, or logs.
//
// Usage:
//   node collect-secret.mjs [--name VAR_NAME[:PREFIX]]... [options]
//
// Options:
//   --name NAME[:PREFIX]  pre-filled variable row; repeat the flag for several
//                         variables. Optional :PREFIX is a HINT only (e.g.
//                         OPENAI_API_KEY:sk-): shown in the placeholder and as
//                         a one-time warning on mismatch — it never blocks
//                         saving. With no --name at all the page starts with
//                         one empty row and the user types the name themselves.
//   --label "..."     page heading (default: the var name, or "Переменные окружения")
//   --hint "..."      optional help text (where to get the keys)
//   --env-path PATH   .env path to write to (default: ./.env)
//                     (named --env-path because node itself intercepts --env-file)
//   --timeout N       seconds to wait before giving up (default: 300)
//   --no-open         do not open the browser, just print the URL
//
// The page lets the user edit variable names, add extra rows («+») and remove
// rows, so one visit can collect any number of NAME=value pairs.
//
// Values are written as-is; a value containing whitespace or special
// characters (# " ' \) is wrapped in double quotes with \ and " escaped, so
// dotenv parsers read it back as a single string.
//
// Security: binds to 127.0.0.1 only; random port + one-time token in the URL;
// accepts a single successful POST, then exits; auto-shutdown on timeout;
// prints only variable names and value lengths, never the values themselves;
// .env written with 600 permissions (POSIX).

import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

// ---------- args ----------
const args = process.argv.slice(2);
function opt(name, def) {
  const i = args.indexOf('--' + name);
  return i >= 0 && args[i + 1] !== undefined ? args[i + 1] : def;
}
const flag = (name) => args.includes('--' + name);

const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const preset = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--name' && args[i + 1] !== undefined) {
    const [name, ...rest] = args[++i].split(':');
    if (!NAME_RE.test(name)) {
      console.error(`ERROR: bad variable name «${name}» (letters, digits, underscore)`);
      process.exit(1);
    }
    preset.push({ name, prefix: rest.join(':') });
  }
}

const LABEL = opt('label', preset.length === 1 ? preset[0].name : 'Переменные окружения');
const HINT = opt('hint', '');
const ENV_FILE = path.resolve(opt('env-path', '.env'));
const TIMEOUT = parseInt(opt('timeout', '300'), 10);

const token = crypto.randomBytes(16).toString('hex');
let done = false;

// ---------- .env writing ----------
function envLine(name, value) {
  if (/[\s"'#\\]/.test(value)) {
    return `${name}="${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
  }
  return `${name}=${value}`;
}

function writeEnvFile(pairs) {
  let text = '';
  if (fs.existsSync(ENV_FILE)) text = fs.readFileSync(ENV_FILE, 'utf8');
  for (const { name, value } of pairs) {
    const line = envLine(name, value);
    const re = new RegExp(`^${name}=.*$`, 'm');
    if (re.test(text)) {
      text = text.replace(re, line);
    } else {
      if (text.length && !text.endsWith('\n')) text += '\n';
      text += line + '\n';
    }
  }
  fs.writeFileSync(ENV_FILE, text);
  try { fs.chmodSync(ENV_FILE, 0o600); } catch { /* windows: no-op */ }

  // advisory: is .env gitignored?
  const dir = path.dirname(ENV_FILE);
  const base = path.basename(ENV_FILE);
  const gi = path.join(dir, '.gitignore');
  const ignored =
    fs.existsSync(gi) &&
    fs.readFileSync(gi, 'utf8').split(/\r?\n/).some((l) => {
      const t = l.trim();
      return t === base || t === '/' + base || t === '.env*' || t === '*.env';
    });
  return ignored ? '' : `WARN: ${base} is not listed in ${gi} — add it before committing`;
}

// ---------- page ----------
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const presetJson = JSON.stringify(preset).replace(/</g, '\\u003c');

const page = `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ввод значений — ${esc(LABEL)}</title>
<style>
  body { background:#101418; color:#eef2f6; font-family:-apple-system,"Segoe UI",Roboto,sans-serif;
         display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; padding:24px; box-sizing:border-box; }
  .card { background:#1a2027; border:1px solid #2a323c; border-radius:20px; padding:40px 38px; max-width:640px; width:100%; }
  h1 { font-size:22px; margin:0 0 14px; }
  .hint { color:#93a1b0; font-size:15px; line-height:1.5; margin:0 0 22px; }
  .row { display:flex; gap:8px; margin-bottom:10px; }
  input { background:#141a20; border:1px solid #2a323c; border-radius:12px; padding:12px 14px;
          color:#eef2f6; font-size:15px; outline:none; font-family:ui-monospace,monospace; min-width:0; }
  input:focus { border-color:#f5a623; }
  input.name { flex:0 0 38%; color:#f5a623; }
  input.val { flex:1; }
  button { border:none; border-radius:12px; font-size:15px; cursor:pointer; }
  .icon { background:#232c36; color:#93a1b0; flex:0 0 auto; width:42px; }
  #add { background:#232c36; color:#93a1b0; padding:11px 16px; margin-top:4px; }
  #save { background:#f5a623; color:#101418; width:100%; margin-top:16px; padding:13px 18px; font-weight:700; font-size:16px; }
  .msg { min-height:1.4em; font-size:14px; margin-top:12px; }
  .msg.err { color:#e5534b; }
  .msg.warn { color:#f5a623; }
  .success { text-align:center; }
  .success .big { font-size:52px; margin-bottom:12px; }
</style></head><body>
<div class="card" id="card">
  <h1>${esc(LABEL)}</h1>
  ${HINT ? `<p class="hint">${esc(HINT)}</p>` : ''}
  <p class="hint">Заполните значения (и при необходимости имена переменных),
  затем нажмите «Сохранить всё». Данные запишутся на этом компьютере
  и не появятся в переписке.</p>
  <div id="rows"></div>
  <button id="add" type="button">+ добавить переменную</button>
  <button id="save" type="button">Сохранить всё</button>
  <div class="msg" id="msg"></div>
</div>
<script>
  const PRESET = ${presetJson};
  const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
  const rows = document.getElementById('rows'), msg = document.getElementById('msg');

  function addRow(name, prefix) {
    const div = document.createElement('div');
    div.className = 'row';
    div.innerHTML = '<input class="name" placeholder="ИМЯ_ПЕРЕМЕННОЙ" spellcheck="false" autocomplete="off">' +
      '<input class="val" type="password" spellcheck="false" autocomplete="off">' +
      '<button class="icon eye" type="button" title="показать">👁</button>' +
      '<button class="icon del" type="button" title="убрать поле">✕</button>';
    div.querySelector('.name').value = name || '';
    div.querySelector('.val').placeholder =
      prefix ? 'Вставьте значение (обычно начинается с ' + prefix + ')' : 'Вставьте значение';
    div.querySelector('.eye').onclick = () => {
      const v = div.querySelector('.val');
      v.type = v.type === 'password' ? 'text' : 'password';
    };
    div.querySelector('.del').onclick = () => {
      if (rows.children.length > 1) div.remove();
    };
    rows.appendChild(div);
    return div;
  }

  (PRESET.length ? PRESET : [{ name: '' }]).forEach((p) => addRow(p.name, p.prefix));
  const first = rows.querySelector(PRESET.length ? '.val' : '.name');
  if (first) first.focus();
  document.getElementById('add').onclick = () => addRow('').querySelector('.name').focus();

  let warned = false;
  rows.addEventListener('input', () => { warned = false; });

  async function save() {
    msg.className = 'msg'; msg.textContent = '';
    const pairs = [], warns = [];
    for (const div of rows.children) {
      const name = div.querySelector('.name').value.trim();
      const value = div.querySelector('.val').value;
      if (!name && !value.trim()) continue; // fully empty row — ignore
      if (!NAME_RE.test(name)) { msg.className = 'msg err';
        msg.textContent = name ? 'имя «' + name + '» — только латиница, цифры и _' : 'у одного из значений не указано имя переменной'; return; }
      if (!value.trim()) { msg.className = 'msg err';
        msg.textContent = 'у переменной ' + name + ' пустое значение'; return; }
      if (pairs.some((p) => p.name === name)) { msg.className = 'msg err';
        msg.textContent = 'переменная ' + name + ' указана дважды'; return; }
      const pre = PRESET.find((x) => x.name === name);
      if (pre && pre.prefix && !value.trim().startsWith(pre.prefix))
        warns.push('значение ' + name + ' обычно начинается с «' + pre.prefix + '»');
      pairs.push({ name, value });
    }
    if (!pairs.length) { msg.className = 'msg err'; msg.textContent = 'нет ни одного заполненного значения'; return; }

    // prefix mismatch is only a recommendation: warn once, save on second click
    if (warns.length && !warned) {
      warned = true;
      msg.className = 'msg warn';
      msg.textContent = warns.join('; ') + ' — проверьте, то ли скопировалось. Если всё верно, нажмите «Сохранить всё» ещё раз.';
      return;
    }

    msg.textContent = 'сохраняю…';
    try {
      const r = await fetch(location.pathname, { method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify({ pairs }) });
      const d = await r.json();
      if (d.ok) {
        document.getElementById('card').innerHTML =
          '<div class="success"><div class="big">✅</div><h1>Сохранено</h1>' +
          '<p class="hint">Эту вкладку можно закрыть и вернуться к диалогу с агентом.</p></div>';
      } else { msg.className = 'msg err'; msg.textContent = d.error || 'не получилось — попробуйте ещё раз'; }
    } catch { msg.className = 'msg err'; msg.textContent = 'нет связи со скриптом — вернитесь к агенту'; }
  }
  document.getElementById('save').onclick = save;
  document.addEventListener('keydown', (e) => { if (e.key === 'Enter') save(); });
</script></body></html>`;

// ---------- server ----------
const server = http.createServer((req, res) => {
  const ok = req.url === '/t/' + token;
  if (!ok) { res.writeHead(404); return res.end('not found'); }

  if (req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end(page);
  }

  if (req.method === 'POST') {
    if (done) { res.writeHead(409); return res.end('{"ok":false,"error":"уже сохранено"}'); }
    let body = '';
    req.on('data', (d) => { body += d; if (body.length > 262144) req.destroy(); });
    req.on('end', () => {
      const fail = (m) => { res.writeHead(200, { 'Content-Type': 'application/json' });
                            res.end(JSON.stringify({ ok: false, error: m })); };
      let pairs = [];
      try { pairs = JSON.parse(body).pairs || []; } catch { /* fallthrough */ }
      if (!Array.isArray(pairs) || !pairs.length) return fail('нет ни одного заполненного значения');

      const seen = new Set();
      const clean = [];
      for (const p of pairs) {
        const name = String(p?.name ?? '').trim();
        let value = String(p?.value ?? '').trim();
        // strip one pair of accidentally copied surrounding quotes
        const m = value.match(/^"(.*)"$/s) || value.match(/^'(.*)'$/s);
        if (m) value = m[1];
        if (!NAME_RE.test(name)) return fail(`некорректное имя переменной «${name}»`);
        if (!value) return fail(`у переменной ${name} пустое значение`);
        if (seen.has(name)) return fail(`переменная ${name} указана дважды`);
        seen.add(name);
        clean.push({ name, value });
      }

      try {
        const warn = writeEnvFile(clean);
        done = true;
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end('{"ok":true}');
        for (const { name, value } of clean)
          console.log(`OK: ${name} saved to ${ENV_FILE} (length ${value.length})`);
        if (warn) console.log(warn);
        setTimeout(() => process.exit(0), 700);
      } catch (e) {
        // client renders this via textContent — plain string is XSS-safe
        fail('не удалось сохранить: ' + String(e.message).slice(0, 200));
      }
    });
    return;
  }

  res.writeHead(405); res.end();
});

server.listen(0, '127.0.0.1', () => {
  const url = `http://127.0.0.1:${server.address().port}/t/${token}`;
  if (flag('no-open')) {
    console.log('PAGE: ' + url);
  } else {
    const cmd = process.platform === 'darwin' ? ['open', [url]]
      : process.platform === 'win32' ? ['cmd', ['/c', 'start', '', url]]
      : ['xdg-open', [url]];
    spawn(cmd[0], cmd[1], { stdio: 'ignore', detached: true }).unref();
    console.log('Страница ввода открыта в браузере. Жду значения…');
  }
});

setTimeout(() => {
  if (!done) { console.error(`TIMEOUT: no values received in ${TIMEOUT}s`); process.exit(1); }
}, TIMEOUT * 1000);
