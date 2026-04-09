#!/usr/bin/env node
/**
 * Cross-platform husky bootstrap.
 *
 * `npm install`이 워크스페이스(apps/web 등)에서 실행될 때 root의 prepare 훅이
 * 호출되는데, 이때 husky가 아직 설치되지 않았거나 git 레포가 아닌 경우에
 * 빌드를 깨뜨리지 않도록 안전하게 처리한다.
 *
 * 정책
 * ----
 * - CI 환경(`CI=true`)에서는 husky 훅을 설치하지 않는다.
 * - husky 패키지가 없거나 `husky install`이 실패해도 exit 0.
 */

import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..');

if (process.env.CI === 'true') {
  console.log('[husky] CI environment detected — skipping hook installation.');
  process.exit(0);
}

if (!existsSync(join(repoRoot, '.git'))) {
  console.log('[husky] No .git directory — skipping hook installation.');
  process.exit(0);
}

const huskyBin = join(
  repoRoot,
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'husky.cmd' : 'husky',
);

if (!existsSync(huskyBin)) {
  console.log('[husky] husky not installed yet — skipping. Run `npm install` at repo root.');
  process.exit(0);
}

const result = spawnSync(huskyBin, ['install'], {
  cwd: repoRoot,
  stdio: 'inherit',
  shell: false,
});

if (result.status !== 0) {
  console.warn(
    `[husky] husky install exited with code ${result.status} — continuing without failing the build.`,
  );
}

process.exit(0);
