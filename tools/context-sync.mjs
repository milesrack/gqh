#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const checkout = resolve(process.env.GQH_CONTEXT_DIR || join(project, '.agent-work/shared'));
const repository = 'https://github.com/milesrack/gqh-systematic-track-context.git';
const args = process.argv.slice(2);
if (args.some(arg => arg !== '--no-refresh')) {
  console.error('Usage: node tools/context-sync.mjs [--no-refresh]');
  process.exit(1);
}
function run(command, argv, capture = false) {
  const result = spawnSync(command, argv, { cwd: project, encoding: 'utf8', stdio: capture ? 'pipe' : 'inherit' });
  if (result.error || result.status !== 0) {
    console.error(result.error?.message || result.stderr || `${command} failed`);
    process.exit(result.status || 1);
  }
  return result.stdout?.trim();
}
if (!existsSync(checkout)) {
  run('git', ['clone', repository, checkout]);
} else {
  const origin = run('git', ['-C', checkout, 'remote', 'get-url', 'origin'], true);
  if (!/^((https:\/\/github\.com\/)|(git@github\.com:))milesrack\/gqh-systematic-track-context(\.git)?$/.test(origin)) {
    console.error(`Refusing to synchronise unrelated repository at ${checkout}.`);
    process.exit(1);
  }
  const branch = run('git', ['-C', checkout, 'branch', '--show-current'], true);
  const dirty = run('git', ['-C', checkout, 'status', '--porcelain'], true);
  if (branch !== 'main' || dirty) {
    console.error('Context checkout must be clean and on main. Preserve and submit note edits through a context PR first.');
    process.exit(1);
  }
  run('git', ['-C', checkout, 'fetch', '--prune', 'origin', 'main']);
  const ahead = Number(run('git', ['-C', checkout, 'rev-list', '--count', 'FETCH_HEAD..HEAD'], true));
  if (ahead) {
    console.error('Context main contains unpublished commits. Preserve them on a feature branch and submit a PR before synchronising.');
    process.exit(1);
  }
  run('git', ['-C', checkout, 'pull', '--ff-only', 'origin', 'main']);
}
if (args.includes('--no-refresh')) {
  console.log('Sources synchronised; search index not refreshed. Run node tools/context.mjs setup or refresh before retrieval.');
} else {
  run(process.execPath, [join(project, 'tools/context.mjs'), 'refresh']);
}
