<script setup>
import H1Region from '../atoms/H1Region.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const { $ProductApiService, $ExploitationApiService } = useNuxtApp();

const props = defineProps({
    exploitation: null
});

const loading = ref(true);
const loadingExploitations = ref(true);
const products = ref([]);

const exploitations = ref([]);
const filter_exploitation = ref([]);
const selectedExploitation = ref(null);

const getProducts = async () => {
    loading.value = true;
    try {
        console.log("selectedExploitation", selectedExploitation.value);
        const response = await $ProductApiService.getProductsPriority(selectedExploitation.value);
        products.value = response;
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
    }
};

const getExploitations = async () => {
    loadingExploitations.value = true;
    try {
        const response = await $ExploitationApiService.getData();
        exploitations.value = response.results;

    } catch (error) {
        console.error(error);
    } finally {
        loadingExploitations.value = false;
    }
};

const handleExploitationChange = (event) => {
    if (selectedExploitation.value == event[0]?.id || event.length == 0) {
        selectedExploitation.value = null;
        filter_exploitation.value = [];
    } else {
        selectedExploitation.value = event[0].id;
        filter_exploitation.value = [{ id: selectedExploitation.value, name: event[0].name }];
    }
    getProducts();
};

onMounted(async () => {
    if (props.exploitation) {
        selectedExploitation.value = props.exploitation.code;
        filter_exploitation.value = [{ id: selectedExploitation.value, name: props.exploitation.label }];
    }
    await getProducts();
    await getExploitations();
});

</script>

<template>
    <div>
        <H1Region>{{ t('pricing_block.products_priority') }}</H1Region>

        <div class="my-2">
            <FilterSelect :options="exploitations" :multiple="false" :filters="filter_exploitation"
                :placeholder="t(`service_block.exploitations`)" @update:modelValue="handleExploitationChange($event)">
                <template #icon>
                    <Icon name="fa6-solid:tree-city" class="text-md ml-2 mr-1" size="10px" />
                </template>
            </FilterSelect>
        </div>

        <div class="mt-4 space-y-3">
            <div v-if="loading" class="rounded border border-slate-200 bg-white px-4 py-3 text-slate-500 shadow-sm">
                {{ t('common.loading') }}...
            </div>
            <div v-else>
                <template v-if="products.length">
                    <div v-for="product in products" :key="product.id"
                        class="rounded border border-slate-200 bg-white px-4 py-3 shadow-sm">
                        <div class="flex items-center justify-between gap-4">
                            <div class="flex flex-col items-start">
                                <span class="text-[11px] uppercase tracking-wide text-slate-500">
                                    {{ t('pricing_block.order_priority') }}
                                </span>
                                <span class="text-xl font-bold text-sky-600">
                                    {{ product.order_priority }}
                                </span>
                            </div>
                            <div class="min-w-0 text-right">
                                <p class="truncate font-semibold text-slate-900">
                                    {{ product.name }}
                                </p>
                                <p class="truncate text-slate-500">
                                    {{ product.exploitation_name }}
                                </p>
                            </div>
                        </div>
                        <div class="mt-2 text-xs text-slate-500 text-right">
                            {{ product.origin_name }}
                        </div>
                    </div>
                </template>
                <div v-else class="rounded border border-dashed border-slate-200 px-4 py-3 text-slate-500">
                    {{ t('common.no_records') }}
                </div>
            </div>
        </div>
    </div>
</template>