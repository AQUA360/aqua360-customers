<script setup>
import { ref, onMounted, onUpdated } from 'vue';
import { useI18n } from 'vue-i18n';
import { searchValues, foundItemTranslation } from '~/utils/search';
import { format } from 'date-fns';
import TimeRelative from '~/components/atoms/TimeRelative.vue';
import CalendarTable from '~/components/molecules/CalendarTable.vue';

const { t } = useI18n()
const sidebarStore = useSidebarStore();

const handleKeydown = (event) => {
    if (event.ctrlKey && event.key === 'k') {
        event.preventDefault();
        sidebarStore.openSearch();
    } else if ((event.key === 'Escape') && sidebarStore.isSearchOpen) {
        event.preventDefault();
        sidebarStore.closeSearch();
    }
};

onMounted(() => {
    window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
});


const username = ref('')
const loading = ref(false);
const groupedSearchHistory = ref({});

const activeSupplyPointToken = ref(localStorage.getItem('config_supply_point_status_activate_token'));
const pendingContractTerminationToken = ref(1);

if (process.client) {
    username.value = localStorage.getItem('user_username') || '';
}

const { $SearchApiService } = useNuxtApp();

const getHistoryData = async () => {
    loading.value = true;
    try {
        const data = await $SearchApiService.getSearchHistory();
        const groupedData = data.results.reduce((acc, item) => {
            const dateKey = format(new Date(item.searched_at), 'yyyy-MM-dd');

            if (!acc[dateKey]) {
                acc[dateKey] = [];
            }
            acc[dateKey].push(item);
            return acc;
        }, {});
        groupedSearchHistory.value = groupedData;
        console.log('groupedSearchHistory.value')
        console.log(Object.entries(groupedSearchHistory.value))
    } catch (error) {
        console.error(`Error fetching:`, error);
    } finally {
        loading.value = false;
    }
}

const getItemTranslation = (item) => {
    const translation = foundItemTranslation(item, 'cat');
    return translation.cat;
};

const handleClick = (event) => {
    try {
        let pathName = '/' + event.app.toLowerCase() + '/' + searchValues[event.entity][0] + '/';
        console.log(pathName)
        navigateTo({
            path: pathName,
            query: {
                action: 'showDetail',
                id: event.item_id,
            }
        })
    } catch (error) {
        console.error(error)
    }
}

const showPage = (path, variables, advance_filters, search) => {
    navigateTo({
        path: path,
        query: {
            action: 'filterPage',
            variables: variables,
            advance_filters: advance_filters,
            search: search
        }
    })
}

onMounted(() => {
    getHistoryData()
})

</script>
<template>
    <div class="space-y-8 w-[60%] mx-auto">
        
        <div class="text-center">
            <h1 class="text-3xl font-semibold text-slate-800">{{ $t('dashboard.welcome') + ', ' + username }}</h1>
        </div>


        <!-- Resum del que l'usuari ha fet avui (cobraments, ordres noves, gestions de
             contracte...), amb enllaç a l'informe complet. -->
        <div class="px-6">
            <MoleculesDailyActivitySummary />
        </div>

        <div class="px-6">
            <span class="text-sm text-slate-500 flex gap-3 px-6 flex items-center ">
                <Icon name="fa6-solid:clock-rotate-left" class="text-slate-500" />
                {{ t("dashboard.recently_visited") }}
            </span>

            <AtomsTabs v-if="Object.entries(groupedSearchHistory).length > 0 && !loading" class="rounded-lg" :is_tab="false">
                <template v-for="[date, results] in Object.entries(groupedSearchHistory)" :key="date">
                    <div>
                        <div class="relative">
                            <div class="flex overflow-hidden space-x-4 py-3 max-w-full scroll-container">
                                <div v-for="(result, index) in results" :key="index" @click="handleClick(result)"
                                    class="flex-shrink-0 py-3 shadow-sm customers-shadow px-4 rounded-lg mx-2 hover:bg-slate-50 cursor-pointer transition duration-200 hover:shadow-md bg-white w-auto inline-block">

                                    <div class="flex items-center gap-3 my-2">
                                        <Icon :name="searchValues[result.entity][1]" size="25px"
                                            class="text-slate-400" />
                                    </div>
                                    <div class="flex items-center gap-3 mb-2">
                                        <span class="text-slate-500 text-sm font-semibold">{{
                                            getItemTranslation(result.found_field) }}:</span>
                                        <span class="text-slate-700 text-base font-medium" v-html="result.found"></span>
                                    </div>

                                    <div class="flex items-center justify-between overflow-x-auto max-w-full">
                                        <div class="flex-shrink-0 text-xs text-slate-400 mb-2">
                                            <span>{{ result.app }} / {{ result.entity.replace(/-/g, ' ') }}</span>
                                        </div>
                                    </div>

                                    <div class="flex items-right justify-end overflow-x-auto max-w-full">
                                        <div class="text-xs text-slate-500">
                                            <TimeRelative :datetime="result.searched_at" />
                                        </div>
                                    </div>
                                </div>
                            </div>

                        </div>
                    </div>
                </template>
            </AtomsTabs>

            <div v-else-if="loading" class="flex justify-center items-center h-full px-6 py-8 rounded-lg customers-shadow mt-4">

                <div class="text-center">
                    <p class="text-slate-500 mb-2 text-lg">
                        {{ t("dashboard.wait") }}
                    </p>
                </div>

            </div>
            <div v-else
                class="flex justify-center items-center h-full px-6 py-8 rounded-lg customers-shadow mt-4">
                <div class="text-center">
                    <h2 class="text-2xl font-semibold text-slate-700 my-2">
                        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500 mr-3" />
                        {{ t("dashboard.no_recent_searches") }}
                    </h2>
                    <p class="text-slate-500 mb-2 text-lg">
                        {{ t("dashboard.no_recent_searches_desc") }}
                    </p>
                    
                </div>
            </div>



        </div>

        <div class="px-6">
            <div class="flex items-center space-x-3 px-6 mb-4">
                <Icon name="fa-regular:lightbulb" class="text-slate-500" size="12px" />
                <span class="text-sm text-slate-500">{{ t('dashboard.relevant_search') }}</span>
            </div>

            <div v-if="!loading" class="customers-shadow rounded-lg p-6 space-y-4">
                <p>
                    <button @click="showPage('contract/contracts', [1], ['variable_type'], null)"
                        class="flex text-left items-center text-sm text-slate-700 hover:text-sky-500 hover:underline transition duration-200">
                        <Icon name="fa-regular:star" size="14px" class="mr-2" />
                        {{ $t('dashboard.relevant_first') }}
                    </button>
                </p>
            </div>

            <div v-else class="rounded-lg p-6 space-y-4">
                <AtomsSkeleton class="w-full" :height="2" :has_icon="false"/>
            </div>
        </div>

        <div class="px-6">
            <div class="flex items-center space-x-3 px-6 mb-4">
                <Icon name="fa6-solid:calendar-days" class="text-slate-500" size="12px" />
                <span class="text-sm text-slate-500">{{ t('dashboard.calendar') }}</span>
            </div>

            <div v-if="!loading" class="customers-shadow rounded-lg p-6 space-y-4">
                <CalendarTable />
            </div>

            <div v-else class="rounded-lg p-6 space-y-4">
                <AtomsSkeleton class="w-full" :height="2" :has_icon="false"/>
            </div>
        </div>



        <div class=" px-6 h-[350px]">
            <span class="text-sm text-slate-500 flex gap-3 px-6 flex items-center">
                <Icon name="fa6-solid:bars-progress" class="text-slate-500" />
                {{ t("dashboard.quick_access") }}
            </span>
            <div class="rounded-lg grid grid-cols-[1fr,1fr] gap-3 h-full pb-2">
                <div class="rounded-lg customers-shadow bg-white p-4 my-4">
                    <span class="text-sm font-semibold text-slate-500 flex gap-3 mb-3">{{ $t('service') }}</span>
                    <div v-if="!loading" class="overflow-y-auto">
                        <NuxtLink to="/service/meters/add"
                            class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                            <abbr :title="$t('service_block.new_meter')" class="no-underline">
                                {{ $t('service_block.new_meter') }}</abbr>
                        </NuxtLink>

                        <NuxtLink to="/service/connection-requests/add"
                            class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                            <abbr :title="$t('service_block.new_connection_request')" class="no-underline">
                                {{ $t('service_block.new_connection_request') }}</abbr>

                        </NuxtLink>

                        <p class="my-2">
                            <button @click="showPage('service/supplypoints', [activeSupplyPointToken], null, null)"
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('dashboard.active_supply_points')" class="no-underline">
                                    {{ $t('dashboard.active_supply_points') }}</abbr>
                            </button>
                        </p>
                        <p class="my-2">
                            <button @click=""
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('dashboard.active_supply_cuts')" class="no-underline">
                                    {{ $t('dashboard.active_supply_cuts') }}</abbr>
                            </button>
                        </p>
                    </div>
                    <div v-else >
                        <AtomsSkeleton class="w-full" :height="5" :has_icon="false"/>
                    </div>
                </div>

                <div class="rounded-lg bg-white customers-shadow p-4 my-4">
                    <span class="text-sm font-semibold text-slate-500 flex gap-3 mb-3">{{ $t('contracting') }}</span>
                    <div v-if="!loading" class="overflow-y-auto">
                        <NuxtLink to="/contract/contract-requests/add"
                            class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                            <abbr :title="$t('contract_block.new_contract')" class="no-underline">
                                {{ $t('contract_block.new_contract') }}</abbr>

                        </NuxtLink>
                        <p class="my-2">
                            <button
                                @click="showPage('contract/contract-terminations', [pendingContractTerminationToken], null, null)"
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('dashboard.pending_contract_terminations')" class="no-underline">
                                    {{ $t('dashboard.pending_contract_terminations') }}</abbr>
                            </button>
                        </p>
                        <!-- <p class="my-2">
                            <button
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('Importar Document ACA de bonificació')" class="no-underline">
                                    {{ $t('Importar Document ACA de bonificació') }}</abbr>
                            </button>
                        </p> -->
                    </div>
                    <div v-else >
                        <AtomsSkeleton class="w-full" :height="5" :has_icon="false"/>
                    </div>
                </div>

            </div>
            <div class="rounded-lg grid grid-cols-[1fr,1fr] gap-3 h-full pb-2">

                <div class="rounded-lg bg-white customers-shadow p-4 my-4">
                    <span class="text-sm font-semibold text-slate-500 flex gap-3 mb-3">{{ $t('billing') }}</span>
                    <div v-if="!loading" class="overflow-y-auto">
                        <p class="my-2">
                            <button
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('dashboard.start_current_batch')" class="no-underline">
                                    {{ $t('dashboard.start_current_batch') }}</abbr>
                            </button>
                        </p>
                        <!-- <p class="my-2">
                            <button
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('Iniciar lot de facturació trimestre actual')" class="no-underline">
                                    {{ $t('Iniciar lot de facturació trimestre actual') }}</abbr>
                            </button>
                        </p> -->
                        <p class="my-2">
                            <button
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('dashboard.unreturned_bails')" class="no-underline">
                                    {{ $t('dashboard.unreturned_bails') }}</abbr>
                            </button>
                        </p>

                    </div>
                    <div v-else >
                        <AtomsSkeleton class="w-full" :height="5" :has_icon="false"/>
                    </div>
                </div>

                <div class="rounded-lg bg-white customers-shadow p-4 my-4">
                    <span class="text-sm font-semibold text-slate-500 flex gap-3 mb-3">{{ $t('work_orders')
                        }}</span>
                    <div v-if="!loading" class="overflow-y-auto">
                        <p class="my-2">
                            <button
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('order_block.new_order')" class="no-underline">
                                    {{ $t('order_block.new_order') }}</abbr>
                            </button>
                        </p>
                        <p class="my-2">
                            <button
                                class="flex text-left w-full gap-3 text-sm items-center font-medium  py-1.5 leading-[14px] hover:bg-slate-200 rounded my-1">
                                <abbr :title="$t('dashboard.pending_orders')" class="no-underline">
                                    {{ $t('dashboard.pending_orders') }}
                                </abbr>
                            </button>
                        </p>
                    </div>
                    <div v-else >
                        <AtomsSkeleton class="w-full" :height="5" :has_icon="false"/>
                    </div>
                </div>

            </div>

        </div>

        <div class="h-[100px]">

        </div>
    </div>
</template>
