<script setup>
import { useI18n } from 'vue-i18n';
import H1Region from '../atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
const { t } = useI18n();

const props = defineProps({
    id: Number      //exploitation id
});
const { $ProductApiService, $ConfiglistApiService, $LineItemTypeApiService } = useNuxtApp();

const error = ref(null);
const loading = ref(false);
const loadingProduct = ref(false);
const loadingStretches = ref(false);

const search = ref('');
const productSearchInput = ref(search.value);
const products = ref([]);
const lineItemTypes = ref([]);
const lineItemTypesCodes = ref([]);
const stretches = ref([]);
const stretchesCodes = ref([]);
const articles = ref([]);
const lineItemSearch = ref('');
const lineItemSearchInput = ref(lineItemSearch.value);
let lineItemSearchTimeout = null;
let productSearchTimeout = null;

const selectedProduct = ref(null);
const selectedLineItemType = ref(null);

const filteredLineItemTypes = computed(() => {
    const query = lineItemSearch.value.trim().toLowerCase();
    if (!query) {
        return lineItemTypes.value;
    }
    return lineItemTypes.value.filter(item => {
        const name = (item.name || '').toLowerCase();
        const rate = (item.price_rate_name || '').toLowerCase();
        return name.includes(query) || rate.includes(query);
    });
});

const getData = async (load = true) => {
    loading.value = load;
    try {
        const response = await $ProductApiService.getAll(search.value, [], 1, null, false, null, [], true, props.id);
        products.value = response;
        getArticles();
    } catch (error) {
        error.value = error;
        console.error(error);
    } finally {
        loading.value = false;
    }
}

const getArticles = async (page = 1, search = '') => {
    try {
        const response = await $ConfiglistApiService.getAll('pricing/article-code', page);
        articles.value = [];
        response.results.forEach(item => {
            articles.value.push({
                value: item.id,
                label: `${item.name} (${item.token})`
            })
        });
        let result = {
            items: articles.value,
            hasNextPage: response && response.next ? true : false
        }
        return result;
    } catch (error) {
        console.error(error);
        articles.value = [];
        return {
            items: articles.value,
            hasNextPage: false
        }
    }
}

const handleProductSearchInput = () => {
    if (productSearchTimeout) {
        clearTimeout(productSearchTimeout);
    }
    productSearchTimeout = setTimeout(() => {
        search.value = productSearchInput.value;
        getData(false);
    }, 200);
};

const handleLineItemSearchInput = () => {
    if (lineItemSearchTimeout) {
        clearTimeout(lineItemSearchTimeout);
    }
    lineItemSearchTimeout = setTimeout(() => {
        lineItemSearch.value = lineItemSearchInput.value;
    }, 100);
};

const resetLineItemSearch = () => {
    lineItemSearch.value = '';
    lineItemSearchInput.value = '';
};

const selectShowingProduct = async (product) => {
    if (selectedProduct.value == product.id) {
        selectedProduct.value = null;
        selectedLineItemType.value = null;
        lineItemTypes.value = [];
        lineItemTypesCodes.value = {};
        stretches.value = [];
        stretchesCodes.value = {};
        resetLineItemSearch();
        return;
    }
    loadingProduct.value = true;
    try {
        selectedProduct.value = product.id;
        const response = await $LineItemTypeApiService.getAllByProduct(product.id);
        lineItemTypes.value = []
        lineItemTypesCodes.value = {}
        resetLineItemSearch();
        response.results.forEach(item => {
            lineItemTypes.value.push(item)
            lineItemTypesCodes.value[item.id] = item.article ? { value: item.article.id, label: `${item.article.name} (${item.article.token})` } : null;
        })
        console.log("lineItemTypes", lineItemTypes.value);
    } catch (error) {
        console.error(error);
        lineItemTypes.value = [];
        lineItemTypesCodes.value = {};
    } finally {
        loadingProduct.value = false;
    }
}

const selectShowingLineItemType = async (lineitem) => {
    if (selectedLineItemType.value == lineitem.id) {
        selectedLineItemType.value = null;
        stretches.value = [];
        stretchesCodes.value = {};
        return;
    }
    loadingStretches.value = true;
    try {
        selectedLineItemType.value = lineitem.id;
        const response = await $LineItemTypeApiService.getStretches(lineitem.id);
        stretches.value = []
        stretchesCodes.value = {}
        response.forEach(item => {
            stretches.value.push(item)
            stretchesCodes.value[item.id] = item.article ? { value: item.article.id, label: `${item.article.name} (${item.article.token})` } : null;
        })
        
    } catch (error) {
        console.error(error);
        stretches.value = [];
        stretchesCodes.value = {};
    } finally {
        loadingStretches.value = false;
    }
}

const updateSelect = async (event, item, isStretch) => {
    if (isStretch) {
        stretchesCodes.value[item.id] = event;
    } else {
        lineItemTypesCodes.value[item.id] = event;
    }

}

const save = async (item, isStretch, stretchFix = false) => {
    try {
        let save_data = {
            id: item.id,
            code: item.code,
            stretch_id: isStretch ? item.id : null,
            line_item_type_id: isStretch ? null : item.id,
            is_fix: stretchFix,
            article_id: isStretch ? stretchesCodes.value[item.id].value : lineItemTypesCodes.value[item.id].value,
        }

        const response = await $LineItemTypeApiService.saveArticle(save_data);
        console.log("response", response);
    } catch (error) {
        console.error("error", error);
    }
}

onMounted(() => {
    getData();
});

watch(() => props.id, () => {
    getData();
});

onUnmounted(() => {
    if (lineItemSearchTimeout) {
        clearTimeout(lineItemSearchTimeout);
    }
    if (productSearchTimeout) {
        clearTimeout(productSearchTimeout);
    }
});


</script>
<template>
    <div class="region__content h-full">
        <H1Region>{{ $t('settings_block.config_article_codes') }}</H1Region>

        <div class="mx-auto flex flex-col gap-5 mt-2">
            <div v-if="loading">
                <AppLoading :text="$t('common.loading')" />
            </div>

            <div v-else-if="error"
                class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-6 text-rose-600 shadow-sm">
                {{ $t('common.error') }}: {{ error.message }}
            </div>

            <template v-else>
                <div class="input-group mb-1 m-2 border-b border-slate-200">
                    <span class="input-group flex flex-start items-center gap-2 w-full">
                        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
                        <input v-model="productSearchInput" @input="handleProductSearchInput" id="searchProduct"
                            type="text" name="search" :placeholder="$t('dashboard.search')"
                            class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
                            autocomplete="off" />
                    </span>
                </div>

                <div v-if="products.length === 0"
                    class="rounded-2xl border border-dashed border-slate-200 bg-white/60 px-4 py-10 text-center text-sm text-slate-500">
                    {{ $t('common.no_data_found') }}
                </div>

                <div v-else class="flex flex-col gap-2">
                    <article v-for="product in products" :key="product.id"
                        class="rounded-2xl border bg-white shadow-sm transition"
                        :class="selectedProduct === product.id ? 'border-sky-500 shadow-md' : 'border-slate-200'">
                        <button
                            class="flex w-full items-center justify-between gap-3 rounded-2xl px-4 py-3 text-left transition hover:bg-sky-50"
                            @click="selectShowingProduct(product)">
                            <div class="flex flex-col gap-1">
                                <p class="text-base font-semibold text-slate-800">{{ product.name }}</p>
                                <p class="text-xs text-slate-500">{{ product.exploitation_name }}</p>
                            </div>
                            <div class="flex h-8 w-8 items-center justify-center rounded-full border text-slate-500 transition"
                                :class="selectedProduct === product.id ? 'border-sky-500 bg-sky-500 text-white' : 'border-slate-200 bg-white'">
                                <Icon
                                    :name="selectedProduct === product.id ? 'fa6-solid:chevron-up' : 'fa6-solid:chevron-down'" />
                            </div>
                        </button>

                        <div v-if="selectedProduct === product.id" class="border-t border-slate-100 bg-slate-50/60">
                            <div v-if="loadingProduct">
                                <AppLoading :text="$t('common.loading')" />
                            </div>

                            <div v-else class="space-y-4 p-4">
                                <div class="input-group mb-4 m-2 border-b border-slate-200">
                                    <span class="input-group flex flex-start items-center gap-2 w-full">
                                        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
                                        <input v-model="lineItemSearchInput" @input="handleLineItemSearchInput"
                                            id="searchProduct" type="text" name="search"
                                            :placeholder="$t('dashboard.search')"
                                            class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
                                            autocomplete="off" />
                                    </span>
                                </div>

                                <p v-if="!filteredLineItemTypes.length"
                                    class="rounded-xl border border-dashed border-slate-200 bg-white/70 px-4 py-6 text-center text-sm text-slate-500">
                                    {{ $t('common.no_data_found') }}
                                </p>

                                <div v-else class="flex flex-col gap-3">
                                    <div v-for="lineItemType in filteredLineItemTypes" :key="lineItemType.id"
                                        class="rounded-xl border bg-white transition"
                                        :class="selectedLineItemType === lineItemType.id ? 'border-sky-500 shadow-md' : 'border-slate-200 shadow-sm'">
                                        <div
                                            class="flex flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between">
                                            <button :disabled="!lineItemType.has_blocks"
                                                class="group flex items-center gap-3 text-left disabled:cursor-not-allowed"
                                                @click="selectShowingLineItemType(lineItemType)">
                                                <div
                                                    class="flex h-9 w-9 items-center justify-center rounded-full border transition group-enabled:border-sky-500 group-enabled:text-sky-500 group-disabled:border-slate-200 group-disabled:text-slate-400">
                                                    <Icon
                                                        :name="selectedLineItemType === lineItemType.id ? 'fa6-solid:chevron-up' : 'fa6-solid:chevron-down'" />
                                                </div>
                                                <div>
                                                    <p
                                                        class="text-xs font-semibold uppercase tracking-wide text-sky-500">
                                                        {{ lineItemType.price_rate_name }}
                                                    </p>
                                                    <p class="text-base font-semibold text-slate-800">
                                                        {{ lineItemType.name }}
                                                    </p>
                                                </div>
                                            </button>

                                            <div
                                                class="flex flex-1 flex-col gap-3 md:flex-row md:items-center md:justify-end">
                                                <div class="w-40">
                                                    <label
                                                        class="block text-xs font-semibold uppercase tracking-wide text-slate-500">{{
                                                            t('pricing_block.article_code') }}</label>
                                                    <input type="text"
                                                        class="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                                                        v-model="lineItemType.code">
                                                </div>
                                                <div class="w-[400px]">
                                                    <AtomsInfiniteScrollVueSelect
                                                        :labelText="t('pricing_block.account_code')"
                                                        :loadFunction="getArticles"
                                                        :item="lineItemTypesCodes[lineItemType.id]"
                                                        @update:modelValue="updateSelect($event, lineItemType, false)" />
                                                </div>
                                                <button @click="save(lineItemType, false)"
                                                    class="mt-5 flex h-9 w-9 items-center justify-center rounded-full border border-sky-500 text-sky-500 transition hover:bg-sky-600 hover:text-white">
                                                    <Icon name="fa6-solid:floppy-disk" class="h-4 w-4" />
                                                </button>
                                            </div>
                                        </div>

                                        <div v-if="selectedLineItemType === lineItemType.id"
                                            class="border-t border-slate-100 bg-slate-50/80">
                                            <div v-if="loadingStretches">
                                                <AppLoading :text="$t('common.loading')" />
                                            </div>

                                            <div v-else class="space-y-3 px-4 py-4">
                                                <div v-for="stretch in stretches" :key="stretch.id"
                                                    class="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
                                                    <div
                                                        class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                                                        <div class="space-y-1 text-sm text-slate-600">
                                                            <p class="font-semibold text-slate-800">
                                                                {{ stretch.stretch }} · {{ stretch.name_stretch }}
                                                            </p>
                                                            <p v-if="stretch.price">
                                                                {{ t('pricing_block.fixed_price') }}:
                                                                {{ formatMoneyWithCurrency(stretch.price) }}
                                                            </p>
                                                            <p v-if="stretch.proportional_price">
                                                                {{ t('pricing_block.short_proportional_price') }}:
                                                                {{ formatMoneyWithCurrency(stretch.proportional_price)
                                                                }}
                                                            </p>
                                                            <p class="text-xs uppercase tracking-wide text-slate-400">
                                                                {{ t('common.limit') }} · {{ stretch.end_stretch }}
                                                            </p>
                                                        </div>
                                                        <div
                                                            class="flex flex-1 flex-col gap-3 md:flex-row md:items-center md:justify-end">
                                                            <div class="w-40">
                                                                <label
                                                                    class="block text-xs font-semibold uppercase tracking-wide text-slate-500">{{
                                                                        t('pricing_block.article_code') }}</label>
                                                                <input type="text"
                                                                    class="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                                                                    v-model="stretch.code">
                                                            </div>
                                                            <div class="w-[400px]">
                                                                <AtomsInfiniteScrollVueSelect
                                                                    :labelText="t('pricing_block.account_code')"
                                                                    :loadFunction="getArticles"
                                                                    :item="stretchesCodes[stretch.id]"
                                                                    @update:modelValue="updateSelect($event, stretch, true)" />
                                                            </div>
                                                            <button
                                                                @click="save(stretch, true, lineItemType.blocks_fix)"
                                                                class="mt-5 flex h-9 w-9 items-center justify-center rounded-full border border-sky-500 text-sky-500 transition hover:bg-sky-600 hover:text-white">
                                                                <Icon name="fa6-solid:floppy-disk" class="h-4 w-4" />
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </article>
                </div>
            </template>
        </div>
    </div>
</template>