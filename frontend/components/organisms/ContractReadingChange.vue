<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import ReadingsChange from '../molecules/ReadingsChange.vue';

import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const route = useRoute()
const router = useRouter()
const { $ContractApiService, $ReadingApiService, $ObservationApiService, $LoggerApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);

const emit = defineEmits(['change', 'show-subregion']);

const loading = ref(false);
const saving = ref(false);

const id = ref(route.params.id)
const contract = ref(null)
const supplyPoints = ref([])

const activeTab = ref(null);

const showRegionComponent = ref('');
const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const readingsToCreate = ref([])
const readingsToUpdate = ref([])
const readingsToDelete = ref([])
const supplyPointLogs = ref({})
const supplyPointDrafts = ref({})

const allowSave = ref(true);


const getData = async function () {
    loading.value = true;
    try {
        const response = await $ContractApiService.getDetail(id.value);
        contract.value = response
        console.log(contract.value);
        supplyPoints.value = contract.value.supply_points;
        activeTab.value = contract.value.supply_point_default.id;
    } catch (error) {
        console.error('Error fetching contract:', error);
    } finally {
        loading.value = false;
    }

}

const save = async () => {
    if (readingsToCreate.value.length == 0 && readingsToDelete.value.length == 0) {
        return navigateTo({
            path: '/contract/contracts/',
            query: {
                id: contract.value.id,
            }
        })
    }

    if (!confirm(t('confirmation_text_block.confirm_apply') + '\n' + t('informative_block.info_changed_readings_control'))) return;
    saving.value = true;
    try {
        const finalLog = Object.values(supplyPointLogs.value).filter(l => l).join('\n\n');

        // Clean previous_reading_option_key to only contain the date (second field in the pipe-separated string)
        const cleanedReadingsData = readingsToCreate.value.map(spData => {
            return {
                ...spData,
                readings: spData.readings.map(reading => {
                    let cleanedKey = reading.previous_reading_option_key;
                    if (cleanedKey && typeof cleanedKey === 'string' && cleanedKey.includes('|')) {
                        const parts = cleanedKey.split('|');
                        if (parts[1]) {
                            cleanedKey = parts[1];
                        }
                    }
                    return {
                        ...reading,
                        previous_reading_option_key: cleanedKey
                    };
                })
            };
        });

        let save_data = {
            readings_data: cleanedReadingsData,
            readings_to_update: readingsToUpdate.value,
            readings_to_delete: readingsToDelete.value,
        }
        const response = await $ReadingApiService.saveModifiedReadings(save_data);
        if (response) {
            if (finalLog) {
                let obsData = {
                    observation: finalLog,
                };
                obsData['contract'] = contract.value.id;
                await $ObservationApiService.postObservation(obsData, 'contract', 'contract');
            }
            toast.success(t('common.correct_save'));
            return navigateTo({
                path: '/contract/contracts/',
                query: {
                    id: contract.value.id,
                }
            })
        } else {
            toast.error(t('common.error_save'));
        }
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
    }

}

const updateReadings = (new_readings, reading_ids, total_estimated_bag, deleted_ids, log) => {
    
    let readings_sp = activeTab.value;
    supplyPointLogs.value[readings_sp] = log;
    supplyPointDrafts.value[readings_sp] = {
        new_readings: _.cloneDeep(new_readings),
        readings_to_delete: [...deleted_ids],
        total_estimated_bag,
    };

    readingsToUpdate.value.push(...reading_ids);
    readingsToUpdate.value = readingsToUpdate.value.filter((id, index, self) => self.indexOf(id) === index);

    readingsToDelete.value.push(...deleted_ids);
    readingsToDelete.value = readingsToDelete.value.filter((id, index, self) => self.indexOf(id) === index && !reading_ids.includes(id));
    
    if (readingsToCreate.value.some(r => r.supply_point_id == readings_sp)) {
        readingsToCreate.value.find(r => r.supply_point_id == readings_sp).readings = new_readings
        readingsToCreate.value.find(r => r.supply_point_id == readings_sp).bag_to_maintain = total_estimated_bag
    } else if (new_readings.length > 0) {
        readingsToCreate.value.push({
            'contract_id': contract.value.id,
            'supply_point_id': readings_sp,
            'readings': new_readings,
            'bag_to_maintain': total_estimated_bag
        })
    }

    if (new_readings.length === 0) {
        readingsToCreate.value = readingsToCreate.value.filter(r => r.supply_point_id !== readings_sp);
    }
}

const closeAllRegions = () => {
    showRegionComponent.value = null;
    regionDetailId.value = null;
    showRegion.value = false;
};

const setActiveTab = (tab) => {
    activeTab.value = tab;
}

const openLogsRegion = () => {
    showRegionComponent.value = 'logs';
    showRegion.value = true;
    fetchReadingLogs(1);
};

const readingLogs = ref([]);
const loadingLogs = ref(false);
const logsTotalCount = ref(0);
const logsCurrentPage = ref(1);
const logsHasNext = ref(false);
const logsHasPrevious = ref(false);

const formatDateLog = (timestamp) => {
    if (!timestamp) return '-';
    try {
        const date = new Date(timestamp);
        return date.toLocaleString();
    } catch (e) {
        return timestamp;
    }
};

const fetchReadingLogs = async (page = 1) => {
    if (!contract.value || !activeTab.value) return;
    const currentSp = contract.value.supply_points.find(sp => sp.id === activeTab.value);
    const meterId = currentSp?.meter_id;
    
    loadingLogs.value = true;
    logsCurrentPage.value = page;
    try {
        const params = {
            contract: contract.value.id,
            page: page
        };
        if (meterId) {
            params.meter = meterId;
        }
        const response = await $LoggerApiService.getReadingChanges(params);
        readingLogs.value = response?.results || [];
        logsTotalCount.value = response?.count || 0;
        logsHasNext.value = !!response?.next;
        logsHasPrevious.value = !!response?.previous;
    } catch (error) {
        console.error('Error fetching reading change logs:', error);
        readingLogs.value = [];
        logsTotalCount.value = 0;
        logsHasNext.value = false;
        logsHasPrevious.value = false;
    } finally {
        loadingLogs.value = false;
    }
};

watch(activeTab, (newVal) => {
    if (newVal) {
        fetchReadingLogs(1);
    }
}, { immediate: true });

const formatObservationLog = (obs) => {
    if (!obs) return '-';
    let formatted = obs;
    if (formatted.includes('Unusually low consumption')) {
        formatted = formatted.replace('Unusually low consumption', t('billing_block.unusually_low_consumption'));
    }
    if (formatted.includes('Unusually high consumption')) {
        formatted = formatted.replace('Unusually high consumption', t('billing_block.unusually_high_consumption'));
    }
    return formatted;
};

onMounted(async () => {
    objectPermissions.value = await checkPermission($ContractApiService);
    if (!objectPermissions.value.can_change) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
    await getData()
});

</script>

<template>
    <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4">
        <div v-if="loading">
            <AppLoading :text="$t('common.loading')" />
        </div>
        <div v-else>
            <div class="flex justify-between items-center mb-6">
                <H1>{{ $t(`billing_block.modify_wrong_readings`) }}: {{ contract.token }}</H1>
                <button @click="openLogsRegion" class="button-secondary flex items-center gap-2">
                    <Icon name="fa6-solid:clock-rotate-left" />
                    <span>{{ $t('billing_block.reading_modifications_history') }}</span>
                </button>
            </div>
            <div class="px-3">
                <span class="text-slate-500">{{ $t(`service_block.available_supply_points`) }}</span>
            </div>
            <div>

                <AtomsTabs>
                    <li v-for="supplyPoint in supplyPoints" :key="supplyPoint.id">
                        <a href="#tab_supply_point_{{ supplyPoint.id }}" @click.prevent="setActiveTab(supplyPoint.id)"
                            :class="{ 'text-sky-600 border-sky-600': activeTab === supplyPoint.id, 'hover:text-gray-600 hover:border-gray-300': activeTab !== supplyPoint.id }">
                            <div>
                                <Icon name="fa6-solid:street-view" class="display-inline mr-2" /> {{
                                    supplyPoint.token }}
                            </div>
                        </a>
                    </li>
                </AtomsTabs>

                <section v-if="activeTab">
                    <ReadingsChange :contract_id="contract.id" :supply_point_id="activeTab" :estimated_bag="contract.estimated_bags.find(e => e.supply_point.id == activeTab)"
                        :persisted_draft="supplyPointDrafts[activeTab] || null" @changed="updateReadings" @allowSave="allowSave = $event" :current_meter_id="contract.supply_points.find(sp => sp.id == activeTab)?.meter_id" />
                </section>

            </div>
            <hr>
            <div class="flex flex-row-reverse mt-4">
                <button @click="save" :disabled="saving || (readingsToCreate.length == 0 && readingsToDelete.length == 0) || !allowSave" class="button-primary">
                    <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
                        $t('common.save') }}
                </button>

            </div>
        </div>

        <div role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10 shadow-2xl"
            :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="showRegion = false"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10 overflow-y-auto h-[calc(100vh-4rem)]">
                <div v-if="showRegionComponent === 'logs'" class="pb-12">
                    <div class="flex items-center justify-between mb-6 pb-4 border-b border-slate-200 dark:border-slate-700">
                        <div class="flex items-center gap-3">
                            <div class="flex items-center justify-center w-12 h-12 rounded-xl bg-sky-100 dark:bg-sky-900/40 text-sky-600 dark:text-sky-400">
                                <Icon name="fa6-solid:clock-rotate-left" class="w-6 h-6" />
                            </div>
                            <div>
                                <h3 class="text-xl font-bold text-slate-800 dark:text-slate-100">
                                    {{ $t('billing_block.reading_modifications_history') }}
                                </h3>
                                <p class="text-xs text-slate-500 dark:text-slate-400">
                                    Registre de canvis realitzats en les lectures d'aquest contracte i comptador
                                </p>
                            </div>
                        </div>
                        <button @click="fetchReadingLogs(1)" class="p-2 text-slate-400 hover:text-sky-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all duration-200" :title="$t('common.refresh') || 'Actualitzar'">
                            <Icon name="fa6-solid:rotate" :class="{ 'animate-spin': loadingLogs }" class="w-5 h-5" />
                        </button>
                    </div>

                    <div v-if="loadingLogs" class="py-12 flex justify-center">
                        <AppLoading :text="$t('common.loading') || 'Carregant històric...'" />
                    </div>
                    <div v-else-if="readingLogs.length === 0" class="py-12 text-center text-slate-400 dark:text-slate-500 text-sm italic bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-dashed border-slate-200 dark:border-slate-700">
                        {{ $t('common.no_data') || 'No hi ha cap modificació registrada per aquest comptador.' }}
                    </div>
                    <div v-else class="space-y-4">
                        <div v-for="log in readingLogs" :key="log.id" class="group bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-100 dark:border-slate-700 shadow-xs hover:border-sky-200 dark:hover:border-sky-900 transition-all duration-200">
                            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 pb-2 border-b border-slate-50 dark:border-slate-700/30">
                                <div class="flex items-center gap-2 flex-wrap">
                                    <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                                        <Icon name="fa6-solid:user" class="w-3 h-3 text-slate-400" />
                                        {{ log.user ? (log.user.first_name ? `${log.user.first_name} ${log.user.last_name}`.trim() : log.user.username) : 'Sistema' }}
                                    </span>
                                    <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-sky-50 dark:bg-sky-950/50 text-sky-700 dark:text-sky-300 border border-sky-100/50 dark:border-sky-900/50">
                                        <Icon name="fa6-regular:calendar" class="w-3 h-3 text-sky-500" />
                                        {{ $t('billing_block.reading_date') || 'Data lectura' }}: <strong class="font-semibold">{{ log.reading_date }}</strong>
                                    </span>
                                </div>
                                <span class="text-xs text-slate-400 flex items-center gap-1">
                                    <Icon name="fa6-regular:clock" class="w-3 h-3" />
                                    {{ formatDateLog(log.timestamp) }}
                                </span>
                            </div>

                            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                <div class="flex items-center gap-3">
                                    <div class="bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 px-3.5 py-2 rounded-xl border border-red-100 dark:border-red-900/30 text-center min-w-[80px]">
                                        <div class="text-[10px] uppercase font-bold text-red-400 dark:text-red-500 tracking-wider">{{ $t('common.previous') || 'Anterior' }}</div>
                                        <div class="font-mono font-bold text-base">{{ log.previous_value !== null ? log.previous_value : '-' }}</div>
                                    </div>
                                    <div class="text-slate-300 dark:text-slate-600 font-bold">➔</div>
                                    <div class="bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 px-3.5 py-2 rounded-xl border border-emerald-100 dark:border-emerald-900/30 text-center min-w-[80px]">
                                        <div class="text-[10px] uppercase font-bold text-emerald-400 dark:text-emerald-500 tracking-wider">{{ $t('common.current') || 'Actual' }}</div>
                                        <div class="font-mono font-bold text-base">{{ log.current_value !== null ? log.current_value : '-' }}</div>
                                    </div>
                                </div>

                                <div v-if="log.observation" class="flex-1 max-w-md bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3 text-xs text-slate-600 dark:text-slate-400 border border-slate-100 dark:border-slate-800">
                                    <span class="font-semibold text-slate-400 dark:text-slate-500 block text-[10px] uppercase mb-1">{{ $t('common.observations') || 'Observacions' }}:</span>
                                    <p class="italic break-words">{{ formatObservationLog(log.observation) }}</p>
                                </div>
                            </div>
                        </div>

                        <!-- Paginació -->
                        <div v-if="logsTotalCount > readingLogs.length || logsCurrentPage > 1" class="flex items-center justify-between pt-6 border-t border-slate-200/60 dark:border-slate-700/60 mt-6">
                            <span class="text-xs text-slate-500 dark:text-slate-400">
                                {{ $t('common.showing_page') || 'Mostrant pàgina' }} <strong class="font-semibold">{{ logsCurrentPage }}</strong> ({{ $t('common.total') || 'Total' }}: {{ logsTotalCount }})
                            </span>
                            <div class="flex items-center gap-1.5">
                                <button @click="fetchReadingLogs(logsCurrentPage - 1)" :disabled="!logsHasPrevious" class="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
                                    {{ $t('common.previous') || 'Anterior' }}
                                </button>
                                <button @click="fetchReadingLogs(logsCurrentPage + 1)" :disabled="!logsHasNext" class="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
                                    {{ $t('common.next') || 'Següent' }}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>