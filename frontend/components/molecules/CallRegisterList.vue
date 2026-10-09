<script setup>
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const props = defineProps({
    contract_id: Number,
    person_id: Number,
    reload: Boolean,
    max_height: {
        type: String,
        default: '40vh'
    },
    // Show a "Download XLSX" button that exports exactly the rows/columns shown.
    exportable: {
        type: Boolean,
        default: true
    },
    exportFileName: {
        type: String,
        default: 'call_register'
    },
});

const emit = defineEmits(['update:count']);
const { $CallRegisterApiService } = useNuxtApp();

console.log('CallRegisterApiService:', $CallRegisterApiService);
const loading = ref(true);
const localData = ref([]);

// Column definitions for the XLSX export — mirror the visible fields above.
const exportColumns = computed(() => [
    { header: t('common.name'), value: (row) => row.person_name, key: 'person_name' },
    { header: t('common.identification'), value: (row) => row.person_token, key: 'person_token' },
    { header: t('contract'), value: (row) => row.contract_token, key: 'contract' },
    { header: t('common.tlf'), value: (row) => row.phone, key: 'phone' },
    { header: t('common.date'), value: (row) => row.time_call ? formatTime(row.time_call) : '', key: 'time_call' },
    { header: t('user'), value: (row) => row.user?.username },
    { header: t('contract_block.has_answered'), value: (row) => row.answered ? t('common.yes') : t('common.no'), key: 'answered' },
    { header: t('common.comment'), value: (row) => row.comment, key: 'comment' },
]);

const getData = async () => {
    try {
        const response = await $CallRegisterApiService.getAll('', 1, props.contract_id || null, props.person_id || null);
        localData.value = response.results;
        emit('update:count', localData.value.length);
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
    }
};


onMounted(async () => {
    await getData();
});

watch(() => props.reload, () => {
    getData();
});

</script>

<template>
    <div class="mt-2 overflow-y-auto" :style="{ maxHeight: props.max_height }">
        <div v-if="loading" class="py-4">
            <AppLoading :text="$t('common.loading')" :size="40" />
        </div>

        <div v-else class="space-y-2">
            <div v-if="exportable && localData?.length > 0" class="flex justify-end mb-1">
                <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName" />
            </div>
            <div v-for="item in localData" :key="item.id"
                class="bg-white border-b border-slate-200 rounded-lg hover:bg-slate-50 transition-all duration-200 overflow-hidden">

                <div class="px-4 py-2">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <h3 class="font-semibold text-slate-900 text-sm truncate">
                                    {{ item.person_name }}
                                </h3>
                                <span class="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                                    {{ item.person_token }}
                                </span>
                            </div>
                            <div v-if="item.contract_token && !props.contract_id" class="flex items-center gap-2 text-slate-600">
                                <span class="text-sm font-mono">
                                    {{ t('contract') }}: {{ item.contract_token }}</span>
                            </div>
                            <div class="flex items-center gap-2 text-slate-600">
                                <Icon name="fa6-solid:phone" class="text-xs" />
                                <span class="text-sm font-mono">{{ item.phone }}</span>
                            </div>
                        </div>

                        <div class="flex flex-col items-end gap-2 flex-shrink-0">
                            <div class="flex items-center gap-1.5 text-slate-600">
                                <Icon name="fa6-solid:clock" class="text-xs" />
                                <span class="text-xs font-medium">{{ formatTime(item.time_call) }}</span>
                                -
                                <span class="text-xs font-medium">{{ item.user.username }}</span>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <div class="relative">
                                    <input v-model="item.answered" type="checkbox" :id="`answered-${item.id}`"
                                        class="sr-only cursor-default" :disabled="true" />
                                    <label :for="`answered-${item.id}`"
                                        class="flex items-center gap-1.5 cursor-default">
                                        <div class="w-4 h-4 border rounded-sm flex items-center justify-center text-slate-500"
                                            :class="item.answered ? 'bg-green-500 border-green-500' : 'bg-white border-slate-300 '">
                                            <Icon v-if="item.answered" name="fa6-solid:check"
                                                class="text-white text-xs" />
                                        </div>
                                        <span class="text-xs text-slate-400 font-medium">
                                            {{ t('contract_block.has_answered') }}
                                        </span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div v-if="item.comment" class="mt-2 px-2 py-1 bg-slate-50 rounded-md">
                        <div class="flex items-center gap-2">
                            <Icon name="fa6-solid:comment" class="text-slate-400 text-xs" />
                            <span class="text-sm text-slate-700 leading-relaxed">{{ item.comment }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="localData.length === 0">
                <div class="footering text-slate-500 p-2">
                    {{ t('common.no_records') }}
                </div>
            </div>
        </div>
    </div>
</template>