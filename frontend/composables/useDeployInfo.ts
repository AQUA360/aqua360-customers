import { computed, ref } from 'vue';
import { formatDateTime } from '~/utils/date';

/**
 * Informació del deploy que s'està executant, per mostrar-la al NavSidebar.
 *
 * Cada repo la genera al servidor amb `scripts/record_deploy.sh` durant el
 * deploy (data del deploy + commit desplegat):
 *
 *  - frontend: `public/deploy-info.json`, servit a `/deploy-info.json`
 *  - backend:  `deploy_info.json`, servit a `/coredata/deploy-info/`
 *
 * En desenvolupament el fitxer del frontend no existeix (no hi ha hagut
 * deploy) i el backend respon amb el commit del git local i `deployed_at`
 * buit; en aquest cas no es mostra res que no sigui cert.
 */

export interface DeployInfo {
    repo?: string;
    deployed_at?: string | null;
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
            const [fe, be] = await Promise.all([fetchFrontend(), fetchBackend()]);
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

    /** Hi ha alguna cosa a mostrar (data de deploy o, com a mínim, un commit). */
    const available = computed<boolean>(() => !!deployedAt.value || hasCommit(frontend.value) || hasCommit(backend.value));

    /** Una línia per repo: `frontend develop@fedb14d4 · 07/09/2026 11:54`. */
    const describe = (info: DeployInfo | null): string => {
        if (!info || !info.commit) return '—';
        const parts = [info.branch ? `${info.branch}@${info.commit}` : info.commit];
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
        available,
        frontendLabel,
        backendLabel,
    };
}
