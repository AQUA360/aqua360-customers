#!/usr/bin/env node
// Escriu `public/deploy-info.json` en construir la imatge (veure el Dockerfile).
//
// La versió, el commit i la data del build arriben com a build args des de
// .github/workflows/imatges.yml: el context del build no porta .git. Sense
// BUILD_DATE (build fet al servidor sense args) es fa servir l'hora actual,
// que és la del build. S'ha d'executar abans de `npm run build`: Nitro només
// serveix els fitxers de `public/` que hi havia en compilar.
import { writeFileSync } from 'node:fs';

const out = process.argv[2];
if (!out) {
    console.error('Ús: node scripts/write-deploy-info.mjs <fitxer de sortida>');
    process.exit(1);
}

const env = (name) => (process.env[name] || '').trim();
const commitFull = env('GIT_COMMIT');

const builtAt = env('BUILD_DATE') || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

const info = {
    repo: 'aqua360-customers',
    component: 'frontend',
    // La data del desplegament la dona el backend (historial); fins aleshores, la del build.
    deployed_at: builtAt,
    built_at: builtAt,
    commit: commitFull.slice(0, 8),
    commit_full: commitFull,
    commit_date: env('GIT_COMMIT_DATE'),
    commit_subject: '',
    branch: env('GIT_BRANCH'),
    release: env('APP_VERSION'),
    source: 'build',
};

writeFileSync(out, `${JSON.stringify(info, null, 2)}\n`);
console.log(JSON.stringify(info));
