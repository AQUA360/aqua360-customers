<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import PersonDetail from '../molecules/PersonDetail.vue';

const { $BillingApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  data: {
    type: Object,
    required: false
  },
  isSubRegion: {
    type: Boolean,
    default: false,
  },
  isRegion: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['show-detail', 'edit', 'changed']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);

const showDetail = (component, id) => {
  emit('show-detail', component, id);
};

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $BillingApiService.getDetail(props.id);
    localData.value = detail;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }

};

onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});

// --- Edició de codi i nom ---
const isEditing = ref(false);
const isSaving = ref(false);
const editToken = ref('');
const editName = ref('');

const startEdit = () => {
  editToken.value = localData.value.token;
  editName.value = localData.value.name;
  isEditing.value = true;
};

const cancelEdit = () => {
  isEditing.value = false;
};

const saveEdit = async () => {
  if (!editToken.value.trim() || !editName.value.trim()) {
    toast.error(t('common.required_fields') || 'Codi i nom són obligatoris');
    return;
  }

  isSaving.value = true;
  try {
    const response = await $BillingApiService.patch(props.id, {
      token: editToken.value.trim(),
      name: editName.value.trim(),
    });

    localData.value.token = response?.token ?? editToken.value.trim();
    localData.value.name = response?.name ?? editName.value.trim();

    isEditing.value = false;
    toast.success(t('common.saved') || 'Desat correctament');
    emit('changed');
  } catch (err) {
    console.error('Error desant els canvis:', err);
    toast.error(t('common.error') || 'Error en desar els canvis');
  } finally {
    isSaving.value = false;
  }
};
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
    }}</span>
  </div>

  <div v-else-if="localData">

    <div v-if="!isEditing" role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.code")' :value=localData.token></FieldDetail>
      <FieldDetail :class="{ 'col-span-2': isRegion }" :label='$t("common.name")'>
        <span class="inline-flex items-center gap-2">
          {{ localData.name }}
          <button @click="startEdit" :title="t('common.edit')"
            class="text-slate-400 hover:text-sky-600 transition-colors duration-200 focus:outline-none">
            <Icon name="fa6-solid:pencil" class="text-sm" />
          </button>
        </span>
      </FieldDetail>
      <FieldDetail :label="$t('billing_block.action')"
        :value="localData.num_templates > 0 ? t('billing_block.by_batch') : t('billing_block.all_supplies')"></FieldDetail>
      <FieldDetail :label='$t("common.status")'>
        <AtomsColorBadge :value=localData.status.name :color=localData.status.color />
      </FieldDetail>
      <FieldDetail :label='$t("billing_block.generated_invoices")' :value="(localData.total_invoices).toString()"></FieldDetail>
    </div>

    <div v-else role="row" class="grid grid-cols-2 gap-4">
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.code') }}</label>
        <input type="text" v-model="editToken" class="input w-full" :disabled="isSaving" />
      </div>
      <div class="mb-2" :class="{ 'col-span-2': isRegion }">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
        <input type="text" v-model="editName" class="input w-full" :disabled="isSaving" />
      </div>
      <div class="col-span-2 flex justify-end gap-2 mt-1">
        <button @click="cancelEdit" class="button-default" :disabled="isSaving">
          {{ t('common.cancel') }}
        </button>
        <button @click="saveEdit" class="button-primary" :disabled="isSaving">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
        </button>
      </div>
    </div>

    <div v-if="isRegion && localData.reading_batches.length > 0" class="mt-2">
      <fieldset class="mb-5 border border-slate-300 rounded-lg">
        <legend class="text-lg font-bold text-slate-600 ml-5">{{ t('billing_block.reading_batches') }}</legend>
        <div class="p-2">
          <div v-for="element in localData.reading_batches" :key="element.id" class="mb-2">
            <div class="flex items-center gap-1 grid grid-cols-2">
              <button v-if="!isSubRegion" @click="showDetail('ReadingBatchRegion', element.id)"
                class="text-left text-sm text-sky-500 underline hover:text-sky-600 hover:no-underline">
                {{ element.token }}</button>
              <span v-else>
                {{ element.token }} 
                <span class="text-slate-400 text-sm">
                  ({{ element.num_total_readings }} {{ t('billing_block.processed_readings') }})
                </span>
              </span>
              <AtomsColorBadge :value=element.status_name :color=element.status_color />
              <!-- <span></span>
              <span class="text-sm text-slate-500 text-right">
                {{ element.num_total_readings }} {{ t('lectures processades') }}</span> -->
            </div>
          </div>
        </div>
      </fieldset>
    </div>
  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>