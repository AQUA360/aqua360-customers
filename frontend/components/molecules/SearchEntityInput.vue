<script setup>

const { t } = useI18n();
const emit = defineEmits(['select']);
const props = defineProps({
    service: Object,
    use_token: {
        type: Boolean,
        default: true,
    },
    title: {
        type: String,
        default: null,
    },
    result_value: {
        type: String,
        default: null,
    },
    disabled: {
        type: Boolean,
        default: false,
    },
    methodName: { 
        type: String,
        default: 'getAll', 
    }
});

const loading = ref(false);
const error = ref(null);

const search_input = ref('');
const search_results = ref([]);
const show_results = ref(false);
const searchContainer = ref(null);

let searchTimeout = null;

const searchData = async () => {
    if (!search_input.value) {
        search_results.value = [];
        loading.value = false;
        return;
    }
    error.value = null;
    try {
        const result = await props.service[props.methodName](search_input.value);
        if (result.results) {
            search_results.value = result.results;
        } else {
            search_results.value = result;
        }
    } catch (err) {
        console.error(err);
        error.value = err;
        search_results.value = [];
    } finally {
        loading.value = false;
    }
};

const debouncedSearch = () => {
    loading.value = true;
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(searchData, 500);
};

const selectResult = (result) => {
    emit('select', result);
    search_input.value = '';
    show_results.value = false;
};

const handleFocus = () => {
    show_results.value = true;
    loading.value = false
};

const handleClickOutside = (event) => {
    if (!searchContainer.value) return;
    if (!searchContainer.value.contains(event.target)) {
        show_results.value = false;
    }
};

onMounted(() => {
    document.addEventListener('click', handleClickOutside);
});

onBeforeUnmount(() => {
    document.removeEventListener('click', handleClickOutside);
    if (searchTimeout) {
        clearTimeout(searchTimeout);
        searchTimeout = null;
    }
});

watch(search_input, (newValue) => {
    debouncedSearch();
});

const noResultsFound = computed(() => {
    return (
        !loading.value &&
        search_input.value &&
        search_results.value.length === 0 &&
        !error.value
    );
});
</script>

<template>
    <div class="relative" ref="searchContainer" >
        <div class="grid grid-cols-[auto,1fr] gap-2 items-center p-2 rounded border border-slate-300" 
        :class="{ 'bg-slate-100' : disabled}">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
            <input
                type="text"
                class="input-text w-full"
                v-model="search_input"
                @focus="handleFocus"
                :placeholder="title ? title : t('dashboard.search')" :disabled="disabled" />
        </div>

        <div v-if="show_results"
            class="absolute z-10 mt-1 w-full bg-white border border-slate-300 rounded shadow-lg max-h-60 overflow-y-auto">
            <div v-if="loading" class="p-2 text-center text-slate-500">
                {{ t('common.loading') }}...
            </div>

            <div v-else-if="error" class="p-2 text-center text-red-500">
                {{ error }}
            </div>
            <div v-else-if="noResultsFound" class="p-2 text-center text-slate-500">
                {{ t('common.no_search_results') }} "{{ search_input }}"
            </div>
            <ul v-else-if="search_results.length > 0">
                <li v-for="(result, index) in search_results" :key="index" @click="selectResult(result)"
                    class="p-2 cursor-pointer hover:bg-slate-100 flex items-center overflow-hidden">
                    <span v-if="use_token" class="font-semibold whitespace-nowrap">
                        {{ result.token }}
                    </span>
                    <span v-if="result_value" class="ml-2 truncate text-slate-600 text-sm">
                        - {{ result[result_value] }}
                    </span>
                    
                </li>
            </ul>
            <div v-else class="p-2 text-center text-slate-500">
                {{ t('common.start_search') }}
            </div>
        </div>
    </div>
</template>