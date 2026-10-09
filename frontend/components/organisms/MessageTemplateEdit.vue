<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $MessageTemplateApiService, $ConfiglistApiService, $CommunicationApiService } = useNuxtApp();

const props = defineProps({
  item: Object,
  isSubRegionOpen: Boolean,
});

const emit = defineEmits(['saved', 'close']);
const SubRegion = ref(false);

const item = ref(props.item);
const name = ref(props.item?.name || '');
const origin = ref(props?.item?.origin? { code: props.item.origin.id, label: props.item.origin.name } : null);

const saving = ref(false);
const attemptedSave = ref(false);
const origins = ref([]);

const save = async () => {
  attemptedSave.value = true;
  if (!isValid.value) return;
  saving.value = true;
  try {

    const save_data = {
      id: item?.value?.id || null,
      name: name.value,
      origin: origin.value.code,
    }
    item.value = await $MessageTemplateApiService.save(save_data);
    emit('saved', item.value);
    resetForm();
  } catch (error) {
    console.error('Error saving bonification type:', error);
  } finally {
    saving.value = false;
    attemptedSave.value = false;
  }
};

const getOrigins = async () => {
  try {
    const result = await $ConfiglistApiService.getAll('communication/message-origin');
    origins.value = result.results.map(origin => ({
      code: origin.id,
      label: origin.name
    }));
  } catch (error) {
    console.error('Error getting origins:', error);
  }
}

const updateSelect = (event) => {
  origin.value = event;
}

const isValid = computed(() => {
  return name.value && origin.value;
});

const resetForm = () => {
  name.value = '';
  origin.value = null;
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($CommunicationApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
});

watch(() => props.item, async (newItem) => {
  objectPermissions.value = await checkPermission($CommunicationApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  await getOrigins();
  if (newItem && newItem.id) { // is editing
    name.value = newItem.name;
    const matchingOrigin = origins.value.find(o => o.code === newItem.origin.id);
    origin.value = matchingOrigin || null;
  } else { // is creating
    resetForm();
  }
}, { immediate: true });

</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion }">
    <div class="flex justify-between">
      <H1Region v-if="item?.id" class="mb-3">{{ t('common.modify') }} {{ t('common.template') }}</H1Region>
      <H1Region v-if="!item?.id" class="mb-3">{{ t('common.new_template') }}</H1Region>
    </div>
    <form @submit.prevent="save">
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
        <input type="text" v-model="name" :class="{ 'invalid': attemptedSave && name == '' }" class="input" />
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.origin') }}</label>
        <v-select id="msg-origin-select" :class="{ 'invalid': attemptedSave && origin == null }"
          class="block w-full required" :model-value="origin" :options="origins"
          @update:modelValue="updateSelect($event)" />
      </div>
      <hr class="mb-2 col-span-3" />
      <div class="col-span-3 flex flex-row-reverse mt-4">
        <button type="submit" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}
        </button>
      </div>
    </form>
  </div>
</template>
