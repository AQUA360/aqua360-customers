import { execFileSync } from 'node:child_process';

/**
 * `/deploy-info.json` en desenvolupament.
 *
 * En producció el fitxer estàtic `public/deploy-info.json`, generat en
 * construir la imatge, té preferència i aquesta ruta no s'arriba a executar;
 * si la imatge no el porta, es respon 404 com abans. En desenvolupament no hi
 * ha build: es llegeix el commit del git local i `deployed_at` queda buit,
 * igual que fa el backend.
 */

const git = (...args: string[]): string => {
    try {
        return execFileSync('git', args, { encoding: 'utf-8', timeout: 5000, stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    } catch {
        return '';
    }
};

export default defineEventHandler(() => {
    if (!import.meta.dev) {
        throw createError({ statusCode: 404 });
    }

    const commitFull = git('rev-parse', 'HEAD');
    if (!commitFull) {
        throw createError({ statusCode: 404 });
    }

    return {
        repo: 'aqua360-customers',
        component: 'frontend',
        deployed_at: null,
        commit: commitFull.slice(0, 8),
        commit_full: commitFull,
        commit_date: git('log', '-1', '--format=%cI'),
        commit_subject: git('log', '-1', '--format=%s'),
        branch: git('rev-parse', '--abbrev-ref', 'HEAD'),
        release: git('describe', '--tags', '--always'),
        source: 'git',
    };
});
