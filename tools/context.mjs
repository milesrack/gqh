#!/usr/bin/env node
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const local = join(root, '.agent-work');
const shared = join(local, 'shared');
const work = process.env.GQH_CONTEXT_DIR
  ? resolve(process.env.GQH_CONTEXT_DIR)
  : existsSync(join(shared, 'notes')) ? shared : local;
const runtime = join(root, 'tools/context-search');
const cli = join(runtime, 'node_modules/@tobilu/qmd/bin/qmd');
const cache = join(process.env.GQH_CONTEXT_DIR ? work : local, '.cache');
const config = join(cache, 'qmd/config');
const args = process.argv.slice(2);

function run(command, argv, options = {}) {
  const result = spawnSync(command, argv, { stdio: 'inherit', ...options });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status || 1);
}

if (!existsSync(join(work, 'notes'))) {
  console.error(`Context library missing at ${work}; copy it or set GQH_CONTEXT_DIR.`);
  process.exit(1);
}
if (args[0] === 'setup') {
  run('npm', ['ci', '--prefix', runtime, '--cache', join(cache, 'npm'), '--no-audit', '--no-fund']);
} else if (!existsSync(cli)) {
  console.error('Run node tools/context.mjs setup first (Node.js >=22 required).');
  process.exit(1);
}

mkdirSync(config, { recursive: true });
// Regenerate machine-specific paths; copied context needs no path edits.
const collections = {
  notes: {
    path: join(work, 'notes'), pattern: '**/*.md',
    context: { '/': 'Competition requirements, market mechanisms and hypothesis notes.' },
  },
};
if (existsSync(join(work, 'library'))) {
  collections.literature = {
    path: join(work, 'library'), pattern: '*/text/**/*.{md,txt}',
    context: { '/': 'Books, papers, handoffs and timestamped podcast transcripts.' },
  };
}
if (existsSync(join(work, 'sources'))) {
  collections.starter = {
    path: join(work, 'sources'), pattern: '*/*-starter/**/*.md',
    context: { '/': 'Official competition starter documentation.' },
  };
}
writeFileSync(join(config, 'context.yml'), JSON.stringify({ collections }, null, 2) + '\n');

const options = {
  cwd: root,
  env: {
    ...process.env,
    QMD_CONFIG_DIR: config,
    INDEX_PATH: join(cache, 'qmd/index.sqlite'),
    XDG_CACHE_HOME: cache,
  },
};
function qmd(argv) {
  run(process.execPath, [cli, '--index', 'context', ...argv], options);
}
if (args[0] === 'setup' || args[0] === 'refresh') {
  qmd(['update']);
  qmd(['embed']);
} else {
  qmd(args);
}
