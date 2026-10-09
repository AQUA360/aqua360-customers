<script setup>
import H1Region from '../atoms/H1Region.vue';
import Pagination from './Pagination.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import { checkPermission } from '~/middleware/permission';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $ConfiglistApiService, $PriceRateApiService } = useNuxtApp();

const emit = defineEmits(['close']);

const pending = ref(false);
const error = ref(null);
const items = ref([]);
const searchQuery = ref('');
const pagination = ref({
    page: 1,
    perPage: 50,
    total: 0,
    totalPages: 0,
    previous: null,
    next: null
});

const getData = async (load = true, page = 1, searchQuery = '') => {
    pending.value = load;
    error.value = null;
    try {
        const response = await $ConfiglistApiService.getAll('statistics/accounting-code/grouped/', page, searchQuery);
        items.value = response.results;
        Object.assign(pagination.value, {
            total: response.count,
            totalPages: Math.ceil(response.count / pagination.value.perPage),
            previous: response.previous,
            next: response.next,
        });

        nextTick(() => {
            const searchEl = document.getElementById('searchInput');
            searchEl?.focus();
        });
    } catch (err) {
        error.value = err;
        console.error(err);
    } finally {
        pending.value = false;
    }
}

const handlePageChange = (newPage) => {
    pagination.value.page = newPage;
    getData(false, newPage, searchQuery.value);
}

const handleSearch = (load = true) => {
    pagination.value.page = 1;
    getData(load, pagination.value.page, searchQuery.value);
}

onMounted(async () => {
    objectPermissions.value = await checkPermission($PriceRateApiService);
    if (!objectPermissions.value.can_view) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
    await getData(true, 1);
});

watch([searchQuery], () => {
    pagination.value.page = 1;
    handleSearch(false);
});

</script>

<template>
    <div class="region__content">
        <div v-if="pending">
            <p>{{ $t('common.loading') }}...</p>
        </div>
        <div v-else-if="error">
            <p>{{ t('common.error') }}: {{ error.message }}</p>
            <p><button @click="getData(pagination.page)" class="underline text-sky-500 hover:no-underline">{{
                $t('common.load_again')
                    }}</button></p>
        </div>
        <div v-else-if="objectPermissions?.can_view">
            <H1Region>{{ t('common.check') }}: {{ $t('pricing_block.account_values') }}</H1Region>

            <span class="input-group flex flex-start items-center gap-2 w-80 mt-3">
                <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
                <input v-model="searchQuery" @input="handleSearch(false)" id="searchInput" type="text" name="search"
                    :placeholder="$t('dashboard.search')"
                    class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
            </span>

            <hr>

            <div class="mt-6 flex justify-center px-2">
                <div id="list" class="w-full overflow-y-auto" :style="{
                    maxHeight: 'calc(100vh - 220px)',
                    minHeight: 'calc(100vh - 220px)',
                }">
                    <ul class="divide-y divide-slate-200 border-b border-slate-200 text-sm">
                        <li v-for="item in items" :key="item.id" class="px-4 py-3">
                            <div class="flex gap-3 grid grid-cols-2 items-start gap-6">
                                <div>
                                    <FieldDetail :label="item.token" :value="item.name" />
                                </div>

                                <div class="min-w-[150px] max-w-xs pl-3" :class="{
                                    'border-l border-slate-200 bg-slate-50': item.values.length > 0,
                                }">
                                    <template v-if="item.values.length > 0">
                                        <details :open="item.values.length <= 2"
                                            class="group rounded border border-slate-200 bg-white px-3 py-2 text-slate-700 shadow-sm">
                                            <summary
                                                class="flex cursor-pointer items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-tight text-slate-500 outline-none">
                                                <span>
                                                    {{ $t('pricing_block.account_values') }} ({{ item.values.length }})
                                                </span>
                                                <span
                                                    class="text-[10px] font-normal text-slate-400 transition-transform group-open:rotate-180">
                                                    &#9660;
                                                </span>
                                            </summary>
                                            <ul class="mt-2 space-y-1 text-[11px] leading-tight text-slate-600 max-h-[200px] overflow-y-auto scrollbar-hide">
                                                <li v-for="i_value in item.values" :key="i_value.id"
                                                    class="flex items-start gap-2">
                                                    <span
                                                        class="w-12 shrink-0 rounded bg-slate-100 px-2 py-1 text-center text-[10px] font-semibold uppercase tracking-tight text-slate-500">
                                                        {{ i_value.token }}
                                                    </span>
                                                    <span class="min-w-0 flex-1 truncate ">
                                                        {{ i_value.description }}
                                                    </span>
                                                </li>
                                            </ul>
                                        </details>
                                    </template>
                                    <p v-else class=" text-slate-500">
                                        {{ $t('pricing_block.variable_value') }}
                                    </p>
                                </div>
                            </div>
                        </li><!-- end for items -->
                    </ul>

                    <div v-if="items.length === 0" class="py-6 text-center text-slate-500">
                        <p>{{ $t('common.no_records') }}</p>
                    </div>

                </div>
            </div>
            <div id="list__footer" class="mt-4 flex justify-center">
                <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
            </div>
        </div>
    </div>
</template>