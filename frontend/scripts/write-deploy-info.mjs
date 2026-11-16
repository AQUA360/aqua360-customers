#!/usr/bin/env node
// Escriu `public/deploy-info.json` en construir la imatge (veure el Dockerfile).
//
// La versió, el commit i la data del build arriben com a build args des de
// .github/workflows/imatges.yml: el context del build no porta .git. Quan la
// imatge es construeix al servidor (sense args), la versió i el commit surten
// del `.git` del servidor: el Dockerfile els deixa a `deploy-git.env`, que es
// passa com a segon argument. Sense BUILD_DATE es fa servir l'hora actual, que
// és la del build. S'ha d'executar abans de `npm run build`: Nitro només
// serveix els fitxers de `public/` que hi havia en compilar.
import { readFileSync, writeFileSync } from 'node:fs';

const [out, gitInfoPath] = process.argv.slice(2);
if (!out) {
    console.error('Ús: node scripts/write-deploy-info.mjs <fitxer de sortida> [deploy-git.env]');
    process.exit(1);
}

// Línies `CLAU=valor`; si el fitxer no hi és, res.
const readGitInfo = (path) => {
    if (!path) return {};
    let text;
    try {
        text = readFileSync(path, 'utf8');
    } catch {
        return {};
    }
    const info = {};
    for (const line of text.split('\n')) {
        const sep = line.indexOf('=');
        if (sep > 0) info[line.slice(0, sep).trim()] = line.slice(sep + 1).trim();
    }
    return info;
};

// Els build args manen; si no porten commit, tot surt del git del servidor (sense barrejar).
const gitInfo = readGitInfo(gitInfoPath);
const fromArgs = !!(process.env.GIT_COMMIT || '').trim() || !gitInfo.GIT_COMMIT;
const env = (name) => ((fromArgs ? process.env[name] : gitInfo[name]) || '').trim();
const commitFull = env('GIT_COMMIT');

const builtAt = (process.env.BUILD_DATE || '').trim() || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

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
