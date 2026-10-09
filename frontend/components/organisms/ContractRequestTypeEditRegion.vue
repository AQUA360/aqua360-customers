<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const { $ContractRequestTypeApiService, $ContractRequestApiService } = useNuxtApp();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  item: Object,
  isSubRegionOpen: Boolean,
});

const emit = defineEmits(['saved', 'close']);
const SubRegion = ref(false);

const item = ref(props.item);
const token = ref(props.item?.token || '');
const name = ref(props.item?.name || '');
const saving = ref(false);

const save = async () => {
  saving.value = true;
  try {
    let exploitation_id = localStorage.getItem('exploitation');
    const save_data = {
      id: item.value.id || null,
      name: name.value,
      token: token.value,
      exploitation: exploitation_id || null,
    }
    item.value = await $ContractRequestTypeApiService.save(save_data);
    emit('saved', item.value);
    resetForm();
  } catch (error) {
    console.error('Error saving bonification type:', error);
  } finally {
    saving.value = false;
  }
};

const resetForm = () => {
  token.value = '';
  name.value = '';
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractRequestApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
});

watch(() => props.item, (newItem) => {
  if (newItem && newItem.id) { // is editing
    token.value = newItem.token;
    name.value = newItem.name;
  } else { // is creating
    resetForm();
  }
}, { immediate: true });

</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion }">
    <div class="flex justify-between">
      <H1Region v-if="item?.id" class="mb-3">{{ t('common.modify') }} {{ t('contract_block.contracting_type') }}</H1Region>
      <H1Region v-if="!item?.id" class="mb-3">{{ t('contract_block.new_contracting_type') }}</H1Region>
    </div>
    <form @submit.prevent="save">
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
        <input type="text" v-model="token" class="input" />
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
        <input type="text" v-model="name" class="input" />
      </div>
      <hr class="mb-2 col-span-3" />
      <div class="col-span-3 flex flex-row-reverse mt-4">
        <button type="submit" :disabled="saving" class="button-primary"><Icon name="fa6-solid:floppy-disk" />&nbsp; {{
          $t('common.save') }}</button>
      </div>
    </form>
  </div>
</template>
