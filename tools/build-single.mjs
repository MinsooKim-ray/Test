#!/usr/bin/env node
// 단일 HTML 빌드: CSS·JS·데이터를 한 파일에 담습니다.
// 사용법: node tools/build-single.mjs "<암호>"
//  → single/ojt-guide.html        (암호화본, 업로드용)
//  → single/ojt-guide-원본.html    (평문, 로컬 보관용 — 업로드 금지)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { webcrypto as crypto } from "node:crypto";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const password = process.argv[2] || process.env.OJT_PASSWORD;
if (!password || password.length < 10) {
  console.error("10자 이상 암호가 필요합니다: node tools/build-single.mjs \"<암호>\"");
  process.exit(1);
}
const read = (p) => readFileSync(path.join(root, p), "utf8");
const dataJs = read("js/data.js");
const sandbox = { window: {} };
vm.runInNewContext(dataJs, sandbox);
const plain = new TextEncoder().encode(JSON.stringify(sandbox.window.OJT_DATA));

const iter = 310000;
const salt = crypto.getRandomValues(new Uint8Array(16));
const iv = crypto.getRandomValues(new Uint8Array(12));
const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveKey"]);
const key = await crypto.subtle.deriveKey({ name: "PBKDF2", salt, iterations: iter, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
const enc = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plain));
const b64 = (u) => Buffer.from(u).toString("base64");
const pkg = JSON.stringify({ v: 1, iter, salt: b64(salt), iv: b64(iv), data: b64(enc) });

const css = read("css/style.css");
const icon = "data:image/svg+xml;base64," + Buffer.from(read("icons/icon.svg")).toString("base64");
// </script> 문자열이 내용에 섞여도 깨지지 않게 처리
const safe = (s) => s.replace(/<\/script/gi, "<\\/script");
const appJs = safe(read("js/app.js").replace(/\/\* ─+ PWA ─+ \*\/[\s\S]*?\n  \}\n/, ""));

function page(dataScript) {
  return read("index.html")
    .replace(/\s*<link rel="manifest"[^>]*>/, "")
    .replace(/<link rel="icon"[^>]*>/, `<link rel="icon" href="${icon}">`)
    .replace(/\s*<link rel="apple-touch-icon"[^>]*>/, "")
    .replace(/<link rel="stylesheet" href="css\/style\.css">/, () => `<style>\n${css}\n</style>`)
    .replace(/\s*<!-- 암호화 빌드[^>]*-->/, "")
    .replace(/<script src="js\/data\.js"><\/script>/, () => dataScript)
    .replace(/<script src="js\/app\.js"><\/script>/, () => `<script>\n${appJs}\n</script>`);
}

const out = path.join(root, "single");
mkdirSync(out, { recursive: true });
writeFileSync(path.join(out, "ojt-guide.html"), page(`<script>window.OJT_ENC = ${pkg};</script>`));
writeFileSync(path.join(out, "ojt-guide-원본.html"), page(`<script>\n${safe(dataJs)}\n</script>`));
console.log("✔ single/ojt-guide.html (암호화·업로드용), single/ojt-guide-원본.html (평문·보관용) 생성");
