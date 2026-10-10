#!/usr/bin/env node
// 암호화 빌드: js/data.js 를 AES-256-GCM(PBKDF2-SHA256) 으로 암호화해 dist/ 에 출력합니다.
// 사용법: node tools/build-secure.mjs "<암호>"   (또는 OJT_PASSWORD 환경변수)
import { readFileSync, writeFileSync, mkdirSync, rmSync, cpSync } from "node:fs";
import { webcrypto as crypto } from "node:crypto";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const password = process.argv[2] || process.env.OJT_PASSWORD;
if (!password || password.length < 10) {
  console.error("10자 이상 암호가 필요합니다: node tools/build-secure.mjs \"<암호>\"");
  process.exit(1);
}

const sandbox = { window: {} };
vm.runInNewContext(readFileSync(path.join(root, "js/data.js"), "utf8"), sandbox);
const plain = new TextEncoder().encode(JSON.stringify(sandbox.window.OJT_DATA));

const iter = 310000;
const salt = crypto.getRandomValues(new Uint8Array(16));
const iv = crypto.getRandomValues(new Uint8Array(12));
const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveKey"]);
const key = await crypto.subtle.deriveKey({ name: "PBKDF2", salt, iterations: iter, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
const data = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plain));
const b64 = (u) => Buffer.from(u).toString("base64");

const dist = path.join(root, "dist");
rmSync(dist, { recursive: true, force: true });
mkdirSync(path.join(dist, "js"), { recursive: true });
for (const p of ["css", "icons", "manifest.webmanifest", "sw.js", ".nojekyll"]) cpSync(path.join(root, p), path.join(dist, p), { recursive: true });
cpSync(path.join(root, "js/app.js"), path.join(dist, "js/app.js"));
const html = readFileSync(path.join(root, "index.html"), "utf8").replace(/\s*<script src="js\/data\.js"><\/script>/, "");
writeFileSync(path.join(dist, "index.html"), html);
writeFileSync(path.join(dist, "data.enc.json"), JSON.stringify({ v: 1, iter, salt: b64(salt), iv: b64(iv), data: b64(data) }));
console.log("✔ dist/ 생성 완료 — dist 폴더만 업로드하세요(평문 data.js 미포함).");
