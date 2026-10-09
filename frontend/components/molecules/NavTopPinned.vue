<script setup>
import { useSidebarStore } from '~/stores/useNavSideBar';
import { useFixedObjectsStore } from '~/stores/useFixedObjects';
import { useExploitationStore } from '~/stores/useExploitationStore';
import GeneralNoteList from '~/components/molecules/GeneralNoteList.vue';
import ContractPinned from '~/components/organisms/ContractPinned.vue';
import CurrentExploitationSelect from '../organisms/CurrentExploitationSelect.vue';
import ExportJobsMenu from '~/components/molecules/ExportJobsMenu.vue';

const sideBarStore = useSidebarStore();
const fixedObjectsStore = useFixedObjectsStore();
const exploitationStore = useExploitationStore();
const { $ContractApiService, $ExploitationApiService } = useNuxtApp();
const { t } = useI18n();

const loading = ref(false);
const showRegion = ref(false);
const isNotesOpen = ref(false);
const isContractPinnedOpen = ref(false);
const isExploitationOpen = ref(false);

const loadingExploitation = ref(false);
const currentExploitation = ref(null);

const toggleNotes = () => {
    closeRegions()
    showRegion.value = true;
    isNotesOpen.value = true;
}

const toggleContractPinned = () => {
    closeRegions()
    if (!currentPinnedContractId.value) {
        return;
    }
    showRegion.value = true;
    isContractPinnedOpen.value = true;
    sideBarStore.togglePinnedContract();
}

const toggleExploitation = () => {
    closeRegions()
    showRegion.value = true;
    isExploitationOpen.value = true;
}

const closeRegions = () => {
    showRegion.value = false;
    isNotesOpen.value = false;
    isContractPinnedOpen.value = false;
    isExploitationOpen.value = false;
    sideBarStore.closePinnedContract();
}

const getPinnedContract = async () => {
    loading.value = true;
    try {
        let contract = await $ContractApiService.getPinnedContract(currentPinnedContractId.value);
        if (contract) {
            fixedObjectsStore.setCurrentPinnedContractId(contract.id);
            fixedObjectsStore.setCurrentPinnedContract(contract);
        }
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
    }
}

const handleExploitationSelected = async () => {
    closeRegions();
    //await unPinContract();
    await getCurrentExploitation();
    window.location.reload()
}

const unPinContract = async () => {
    try {
        if (!currentPinnedContractId.value) return;
        let save_data = {
            id: currentPinnedContractId.value,
            is_pinned: false
        }
        fixedObjectsStore.clearCurrentPinnedContract();
        let contract = await $ContractApiService.save(save_data);
    } catch (error) {
        console.error(error);
    }
}

const getCurrentExploitation = async () => {
    loadingExploitation.value = true;
    try {
        let exploitation_id = localStorage.getItem('exploitation');
        if (!exploitation_id) {
            // Autoselecció NOMÉS a les instal·lacions que declaren germanes (taula ExploitationSite
            // amb files) i que tenen una sola explotació: allà triar-la a mà no aporta res. Als
            // clients amb la taula buida, o amb diverses explotacions a la mateixa base de dades,
            // no es toca res i la barra segueix dient que no n'hi ha cap seleccionada — l'app no ha
            // de triar per l'usuari. Mateixa condició d'una sola explotació que ja fa servir
            // `NavSidebar.vue`. Es comprova només quan no hi ha res triat, no a cada càrrega.
            // suppressToast a les dues crides: un usuari sense el permís `view_exploitation` rebria
            // un 403 i, sense silenciar-lo, un toast vermell a cada càrrega. Si falla, no se
            // selecciona res, que és el comportament de sempre.
            // A una instal·lació única no hi ha res a autoseleccionar, i com que `localStorage` es
            // queda buit per sempre, sense recordar-ho es preguntaria per les germanes a cada
            // càrrega de pàgina. Es demana un sol cop per sessió del navegador; si la crida falla
            // (`null`) no es recorda res i es torna a intentar més endavant.
            const cacheKey = 'exploitation_sites_absent';
            const sites = sessionStorage.getItem(cacheKey) === '1'
                ? { results: [] }
                : await $ExploitationApiService.getSites().catch(() => null);
            if (sites?.results?.length) {
                const data = await $ExploitationApiService.getData('', 1, 'token', false, true);
                if (data?.results?.length === 1 && data.results[0]?.id) {
                    localStorage.setItem('exploitation', data.results[0].id);
                    exploitation_id = data.results[0].id;
                }
            } else if (sites) {
                sessionStorage.setItem(cacheKey, '1');
            }
        }
        if (exploitation_id) {
            currentExploitation.value = await $ExploitationApiService.getDetail(exploitation_id);
        }
        exploitationStore.setCurrent(currentExploitation.value);
    } catch (error) {
        console.error(error);
    } finally {
        loadingExploitation.value = false;
    }
}

const goToPinnedContract = () => {
    navigateTo({
        path: '/contract/contracts/pinned',
        query: {
            action: 'showDetail',
        }
    })
}

onMounted(() => {
    getPinnedContract();
    getCurrentExploitation();
});

const currentPinnedContractId = computed(() => fixedObjectsStore.currentPinnedContractId);
const sideIsPinnedContractOpen = computed(() => sideBarStore.isPinnedContractOpen);

watch(currentPinnedContractId, (newVal) => {
    if (newVal) {
        getPinnedContract();
    }
});

watch(sideIsPinnedContractOpen, (newVal) => {
    if (sideBarStore.isPinnedContractOpen) {
        toggleContractPinned()
    } else {
        closeRegions();
    }
});

</script>
<template>
    <div class="flex items-center justify-end gap-2">
        <button @click="toggleExploitation" :disabled="loadingExploitation"
            class="enabled:cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 w-auto bg-white rounded-lg px-3 hover:bg-slate-200 flex items-center justify-between gap-4">
            <div class="flex justify-end w-full">
                <div class="flex items-center gap-3">
                    <Icon name="fa6-solid:tree-city" class="w-5 h-5 text-slate-600" />
                    <span class="text-slate-600" :class="{'text-red-500 font-bold': !currentExploitation}">
                        {{ currentExploitation? currentExploitation.name: t('common.no_selected_exploitation') }}
                    </span>
                </div>
            </div>
        </button>
        <NuxtLink v-if="fixedObjectsStore.currentPinnedContract" :to="`/contract/contracts/${currentPinnedContractId}/pinned/`"
            class="group flex items-center justify-center rounded w-6 h-6 border border-slate-200 hover:bg-slate-100">
            <Icon name="fa6-solid:arrow-up-right-from-square" class="w-3.5 h-3.5 group-hover:text-sky-500 text-slate-400" />
        </NuxtLink>
        
        <button v-if="fixedObjectsStore.currentPinnedContract" @click="toggleContractPinned"
            class="cursor-pointer w-[50%] bg-white rounded-lg border border-slate-200 px-3 hover:bg-slate-100 flex items-center justify-between gap-4">
            <div class="flex justify-between w-full">
                <div class="flex items-center gap-3">
                    <Icon name="ic:sharp-push-pin" class="w-5 h-5 text-sky-500" />
                    <span class="text-slate-800 font-semibold">
                        <AtomsContractBadge class="cursor-pointer" :contract="fixedObjectsStore.currentPinnedContract"
                            :color="'white'" />
                    </span>
                    <span class="text-slate-600 text-sm truncate px-2">
                        {{ fixedObjectsStore.currentPinnedContract.holder_full }}
                    </span>
                </div>
                <kbd class="px-1 my-0.5 items-center flex text-xs font-light text-slate-400 border border-slate-300 rounded-lg">
                    Ctrl p</kbd>

            </div>
        </button>
       
        <ExportJobsMenu />

        <div>
            <abbr :title="t('dashboard.general_notes')">
                <button @click="toggleNotes" class="group flex items-center justify-center rounded w-6 h-6  border"
                    :class="{
                        'border-sky-200 hover:bg-sky-100': sideBarStore.newGeneralNotes > 0,
                        'border-slate-200 hover:bg-slate-100': sideBarStore.newGeneralNotes == 0
                    }">
                    <Icon name="fa6-solid:comment" class="w-3.5 h-3.5 group-hover:text-slate-500" :class="{
                        'text-sky-400 animate-bounce': sideBarStore.newGeneralNotes > 0,
                        'text-slate-400': sideBarStore.newGeneralNotes == 0
                    }" />
                </button>
            </abbr>
        </div>
    </div>

    <div role="region" id="right_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 w-[40%] z-20 ease py-2 text-base bg-white overflow-x-hidden overflow-y-auto scrollbar-hide"
        :class="{
            'translate-x-0': showRegion,
            'translate-x-[2000px]': !showRegion,
            'w-[40%]': showRegion && isNotesOpen,
            'w-[94%]': showRegion && isContractPinnedOpen,
        }">
        <div id="region_nav" class="mb-3 px-3">
            <button @click="closeRegions" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                <Icon name="fa6-solid:angles-right" class="text-slate-500" />
            </button>
        </div>
        <div class="px-10">
            <GeneralNoteList v-if="isNotesOpen" />
            <ContractPinned v-if="isContractPinnedOpen" :isSubRegion="true" :id="currentPinnedContractId"
                @close="closeRegions" />
            <CurrentExploitationSelect v-if="isExploitationOpen" :id="currentExploitation?.id" @close="handleExploitationSelected" />
        </div>
    </div>

</template>