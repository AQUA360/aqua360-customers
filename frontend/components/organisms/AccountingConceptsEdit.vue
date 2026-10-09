<script setup>
import H1Region from '~/components/atoms/H1Region.vue';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';

const { t } = useI18n();
const objectPermissions = ref(null);
const toast = useToast();

const props = defineProps({
    id: {
        type: Number,
        default: null,
    },
});
const { $AccountingConceptApiService, $PriceRateApiService, $AccountingTypeApiService } = useNuxtApp();
const emit = defineEmits(['change']);
const loading = ref(false);
const loadingTypes = ref(false);
const saving = ref(false);
const attemptedSave = ref(false);

const token = ref(null);
const name = ref(null);
const category = ref(null);
const selectedType = ref(null);
const addTaxes = ref(false);
const addSubtotal = ref(false);

const types = ref([]);
const categories = ref([
    { value: 'invoice', label: t('invoice'), description: t('pricing_block.category_invoice_description'), icon: 'fa6-solid:file-invoice' },
    { value: 'lineitem', label: t('pricing_block.line_items'), description: t('pricing_block.category_line_items_description'), icon: 'fa6-solid:list' },
    { value: 'payment', label: t('payments'), description: t('pricing_block.category_payments_description'), icon: 'fa6-solid:credit-card' },
]);

const loadTypes = async () => {
    loadingTypes.value = true;
    try {
        const response = await $AccountingTypeApiService.getAll();
        response.results.forEach(type => {
            types.value.push({
                value: type.id,
                label: type.name,
                add_taxes: type.add_taxes,
                add_subtotals: type.add_subtotals,
            });
        });
    } catch (error) {
        console.error(error);
        toast.error(t('common.error_loading_data'));
    } finally {
        loadingTypes.value = false;
    }
};

const getData = async () => {
    await loadTypes();
    if (!props.id) return;
    loading.value = true;
    try {
        const response = await $AccountingConceptApiService.getDetail(props.id);
        token.value = response.token;
        name.value = response.name;
        category.value = categories.value.find(cat => cat.value === response.category);
        selectedType.value = types.value.find(type => type.value === response.type?.id);
    } catch (error) {
        console.error(error);
        toast.error(t('common.error_loading_data'));
    } finally {
        loading.value = false;
    }
};

const save = async () => {
    attemptedSave.value = true;
    if (!isValid.value) return;
    saving.value = true;
    try {
        const payload = {
            id: props.id,
            token: token.value,
            name: name.value,
            type_id: selectedType.value?.value,
            category: category.value?.value,
        }
        const response = await $AccountingConceptApiService.save(payload);
        if (response) {
            toast.success(t('common.saved_successfully'));
            emit('change');
        }
    } catch (error) {
        console.error(error);
        toast.error(t('common.error_saving_data'));
    } finally {
        saving.value = false;
    }
};

const isValid = computed(() => {
    return token.value && name.value && selectedType.value && category.value;
});

onMounted(async () => {
    objectPermissions.value = await checkPermission($PriceRateApiService);
    if (!objectPermissions.value.can_change) {
        toast.error(t('common.no_permissions'));
        emit('close');
        return;
    }
    await getData();
});

</script>

<template>
    <div>
        <H1Region>{{ props.id ? t('pricing_block.edit_accounting_concept') : t('pricing_block.new_accounting_concept')
            }}</H1Region>

        <div class="flex items-center grid grid-cols-2 gap-x-4 gap-y-2 mt-3">
            <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-slate-500">{{ t('common.identificator') }}</label>
                <input type="text" class="input" v-model="token"
                    :class="{ 'invalid': attemptedSave && !token }" />
            </div>
            <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-slate-500">{{ t('common.name') }}</label>
                <input type="text" class="input" v-model="name" :class="{ 'invalid': attemptedSave && !name }" />
            </div>
            <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-slate-500">{{ t('common.type') }}</label>
                <v-select v-model="selectedType" class="block w-full custom-select" :options="types"
                    :loading="loadingTypes" :disabled="loadingTypes || loading || types.length === 0"
                    :class="{ 'invalid': attemptedSave && !selectedType }" />
            </div>
            <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-slate-500">{{ t('billing_block.category') }}</label>
                <v-select v-model="category" class="block w-full custom-select" :options="categories"
                    :disabled="loading" :class="{ 'invalid': attemptedSave && !category }" />
            </div>
        </div>

        <dl class="mt-5 divide-y divide-sky-100 overflow-hidden rounded-md border border-sky-200 bg-white">
            <div v-for="cat in categories" :key="cat.value"
                class="flex items-start gap-2 border-l-2 px-2.5 py-1.5 transition-colors bg-sky-50" :class="category?.value === cat.value
                    ? 'border-l-sky-600 bg-sky-50'
                    : 'border-l-transparent'">
                <dt class="flex w-[7.25rem] shrink-0 items-center gap-1.5">
                    <span class="flex size-5 shrink-0 items-center justify-center rounded-sm bg-sky-100 text-sky-700">
                        <Icon :name="cat.icon" class="size-2.5" />
                    </span>
                    <span class="truncate text-[11px] font-semibold leading-tight text-sky-950">{{ cat.label }}</span>
                </dt>
                <dd class="min-w-0 text-[11px] leading-snug text-sky-700">{{ cat.description }}</dd>
            </div>
        </dl>

        <hr class="my-3" />

        <div class="flex flex-row-reverse">
            <button type="button" class="button-primary flex items-center gap-x-2 w-fit" :disabled="saving"
                @click="save">
                <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" class="size-3 shrink-0"
                    :class="{ 'animate-spin': saving }" />
                {{ t('common.save') }}
            </button>

        </div>

    </div>
</template>