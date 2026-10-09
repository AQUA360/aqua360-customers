<!-- components/organisms/ClauseTemplateEditRegion.vue -->
<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $ClauseTemplateApiService, $ContractRequestApiService } = useNuxtApp();

const props = defineProps({
  item: Object,
});

const emit = defineEmits(['saved', 'deleted', 'close']);

const token = ref('');
const title = ref('');
const clause = ref('');
const saving = ref(false);
const deleting = ref(false);

// Logical delete: existing contract clauses keep their copied text
const deleteTemplate = async () => {
  if (!confirm(t('contract_block.confirm_delete_clause_template'))) {
    return;
  }
  deleting.value = true;
  try {
    await $ClauseTemplateApiService.save({ id: props.item.id, is_active: false });
    toast.success(t('common.deleted_successfully'));
    emit('deleted', props.item);
  } catch (error) {
    console.error('Error deleting clause template:', error);
    toast.error(t('common.error'));
  } finally {
    deleting.value = false;
  }
};

const save = async () => {
  if (!title.value.trim() || !clause.value.trim()) {
    toast.error(t('common.required_fields'));
    return;
  }
  saving.value = true;
  try {
    const saveData = {
      token: token.value,
      title: title.value,
      clause: clause.value,
    };
    if (props.item?.id) {
      saveData.id = props.item.id;
    }
    const saved = await $ClauseTemplateApiService.save(saveData);
    toast.success(t('common.saved_successfully'));
    emit('saved', saved);
  } catch (error) {
    console.error('Error saving clause template:', error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractRequestApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close');
  }
});

const resetForm = () => {
  token.value = '';
  title.value = '';
  clause.value = '';
};

watch(() => props.item, (newItem) => {
  if (newItem && newItem.id) { // is editing
    token.value = newItem.token || '';
    title.value = newItem.title || '';
    clause.value = newItem.clause || '';
  } else { // is creating
    resetForm();
  }
}, { immediate: true });

</script>

<template>
  <div class="region__content pr-10">
    <div class="flex justify-between">
      <H1Region v-if="item?.id" class="mb-3">{{ $t('common.modify') }} {{ t('contract_block.clause_template').toLowerCase() }}</H1Region>
      <H1Region v-if="!item?.id" class="mb-3">{{ t('contract_block.new_clause_template') }}</H1Region>
    </div>
    <p v-if="item?.id" class="mb-4 p-2 text-sm bg-yellow-50 text-slate-600 border border-yellow-200 rounded">
      <Icon name="fa6-solid:circle-info" class="text-slate-500" />&nbsp;
      {{ t('contract_block.clause_template_edit_notice') }}
    </p>
    <form @submit.prevent="save">
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
        <input type="text" v-model="token" class="input" />
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.title') }} *</label>
        <input type="text" v-model="title" maxlength="255" class="input" required />
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.text') }} *</label>
        <textarea v-model="clause" rows="16" required
          class="w-full p-2 rounded border border-slate-300 bg-white text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-400"></textarea>
      </div>
      <hr class="mb-2" />
      <div class="flex flex-row-reverse justify-between mt-4">
        <button type="submit" :disabled="saving || deleting" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
        <button v-if="item?.id" type="button" :disabled="saving || deleting" @click="deleteTemplate"
          class="px-3 py-1 rounded border border-red-300 text-red-600 hover:bg-red-50 active:bg-red-100">
          <Icon name="fa6-solid:trash-can" />&nbsp; {{ $t('common.delete') }}
        </button>
      </div>
    </form>
  </div>
</template>
