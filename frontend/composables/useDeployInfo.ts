import { computed, ref } from 'vue';
import { formatDateTime } from '~/utils/date';

/**
 * Informació del deploy que s'està executant, per mostrar-la al NavSidebar.
 *
 * La versió, el commit i la data del build es generen en construir cada imatge
 * (veure `.github/workflows/imatges.yml` i els Dockerfile):
 *
 *  - frontend: `public/deploy-info.json`, servit a `/deploy-info.json`
 *  - backend:  `deploy_info.json`, servit a `/coredata/deploy-info/`
 *
 * La data del desplegament al client (`deployed_at`) la dona el backend, de
 * l'historial de versions que s'hi han executat: la del frontend, quan aquest
 * li envia la seva versió (POST a `/coredata/deploy-info/`).
 *
 * En desenvolupament no hi ha build: tots dos responen amb el commit del git
 * local i `deployed_at` buit (el del frontend, `server/routes/deploy-info.json.ts`);
 * en aquest cas no es mostra res que no sigui cert.
 */

export interface DeployInfo {
    repo?: string;
    component?: string;
    deployed_at?: string | null;
    built_at?: string | null;
    commit?: string;
    commit_full?: string;
    commit_date?: string;
    commit_subject?: string;
    branch?: string;
    release?: string;
    source?: string;
}

// Estat compartit: n'hi ha prou amb demanar-ho un cop per sessió de navegador.
const frontend = ref<DeployInfo | null>(null);
const backend = ref<DeployInfo | null>(null);
const loaded = ref(false);
let inFlight: Promise<void> | null = null;

const hasCommit = (info: DeployInfo | null): boolean => !!info?.commit;

/**
 * Versió per mostrar: la release o, en una imatge de branca, la darrera release
 * i la branca (`v1.152.01 + develop (abcdef12)`). Les imatges antigues de branca
 * porten `git describe` (`v1.152.01-5-gabcdef12`): se'n treu la release.
 */
export const versionLabel = (info: DeployInfo | null): string => {
    if (!info) return '';
    const release = (info.release || '').replace(/-\d+-g[0-9a-f]+$/, '');
    if (!info.branch) return release || info.commit || '';
    const branch = info.commit ? `${info.branch} (${info.commit})` : info.branch;
    return release ? `${release} + ${branch}` : branch;
};

/** Frontend i backend són del mateix monorepo: si tots dos tenen commit, han de coincidir. */
const sameVersion = (a: DeployInfo | null, b: DeployInfo | null): boolean => {
    if (a?.commit && b?.commit) return a.commit === b.commit;
    if (a?.release && b?.release) return a.release === b.release;
    return true;
};

export function useDeployInfo() {
    const { $apiManager } = useNuxtApp();
    const config = useRuntimeConfig();

    const fetchFrontend = async (): Promise<DeployInfo | null> => {
        try {
            // Fitxer estàtic del propi frontend; `cache: 'no-store'` perquè un
            // deploy nou no quedi amagat darrere la cau del navegador.
            const data = await $fetch<DeployInfo>('/deploy-info.json', { cache: 'no-store' });
            return data && typeof data === 'object' ? data : null;
        } catch (error) {
            // Sense deploy (desenvolupament) el fitxer no existeix: no és un error.
            return null;
        }
    };

    /** El frontend informa el backend de la seva versió i en rep la data del desplegament. */
    const reportFrontend = async (info: DeployInfo): Promise<DeployInfo> => {
        if (info.source === 'git' || (!info.commit && !info.release)) return info;
        try {
            const data = await $apiManager.fetch(
                `${config.public.apiHost}/coredata/deploy-info/`,
                'POST',
                {
                    release: info.release || '',
                    commit: info.commit || '',
                    commit_full: info.commit_full || '',
                    branch: info.branch || '',
                    built_at: info.built_at || info.deployed_at || null,
                    source: info.source || 'build',
                },
                null,
                true, // suppressToast
            );
            return data?.deployed_at ? { ...info, deployed_at: data.deployed_at } : info;
        } catch (error) {
            return info;
        }
    };

    const fetchBackend = async (): Promise<DeployInfo | null> => {
        try {
            const data = await $apiManager.fetch(
                `${config.public.apiHost}/coredata/deploy-info/`,
                'GET',
                null,
                null,
                true, // suppressToast: no ha de molestar si no hi arriba
            );
            return data && typeof data === 'object' ? data : null;
        } catch (error) {
            return null;
        }
    };

    /** Carrega la informació dels dos repos un únic cop (crides simultànies comparteixen la promesa). */
    const load = (): Promise<void> => {
        if (inFlight) return inFlight;

        inFlight = (async () => {
            const [fe, be] = await Promise.all([
                fetchFrontend().then((info) => (info ? reportFrontend(info) : null)),
                fetchBackend(),
            ]);
            frontend.value = fe;
            backend.value = be;
            loaded.value = true;
        })();

        return inFlight;
    };

    /** Data de deploy a mostrar: la més recent de les dues (frontend i backend es despleguen per separat). */
    const deployedAt = computed<string | null>(() => {
        const dates = [frontend.value?.deployed_at, backend.value?.deployed_at]
            .filter((d): d is string => !!d);
        if (!dates.length) return null;
        return dates.reduce((a, b) => (new Date(a) > new Date(b) ? a : b));
    });

    const deployedAtLabel = computed<string>(() => (deployedAt.value ? formatDateTime(deployedAt.value) : ''));

    /** Versió desplegada (monorepo: una sola versió). Si frontend i backend no coincideixen, `mismatch` ho indica. */
    const version = computed<string>(() => versionLabel(frontend.value) || versionLabel(backend.value));

    /** Frontend i backend en versions diferents (p. ex. només se n'ha actualitzat un). */
    const mismatch = computed<boolean>(() => !!frontend.value && !!backend.value && !sameVersion(frontend.value, backend.value));

    /** Línia principal: `v1.152.01 · 07/09/2026 11:54` (el que hi hagi de les dues parts). */
    const summaryLabel = computed<string>(() => [version.value, deployedAtLabel.value].filter(Boolean).join(' · '));

    /** Hi ha alguna cosa a mostrar (data de deploy, versió o, com a mínim, un commit). */
    const available = computed<boolean>(() => !!deployedAt.value || !!version.value || hasCommit(frontend.value) || hasCommit(backend.value));

    /** Una línia per part: `v1.152.01 (fedb14d4) · 07/09/2026 11:54`. */
    const describe = (info: DeployInfo | null): string => {
        if (!info || (!info.commit && !info.release && !info.deployed_at)) return '—';
        const parts: string[] = [];
        const label = versionLabel(info);
        // En una imatge de release, el commit hi va entre parèntesis; en una de branca ja hi és.
        if (label) parts.push(!info.branch && info.commit && label !== info.commit ? `${label} (${info.commit})` : label);
        if (info.deployed_at) parts.push(formatDateTime(info.deployed_at));
        else if (info.commit_date) parts.push(formatDateTime(info.commit_date));
        return parts.join(' · ');
    };

    const frontendLabel = computed<string>(() => describe(frontend.value));
    const backendLabel = computed<string>(() => describe(backend.value));

    return {
        frontend,
        backend,
        loaded,
        load,
        deployedAt,
        deployedAtLabel,
        version,
        summaryLabel,
        available,
        mismatch,
        frontendLabel,
        backendLabel,
    };
}
