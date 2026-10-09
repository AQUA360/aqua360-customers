<script setup>
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $OrderTypeApiService, $OrderApiService } = useNuxtApp();

const props = defineProps({
  item: Object,
  isSubRegionOpen: Boolean,
});

const emit = defineEmits(['saved', 'deleted', 'close']);
const SubRegion = ref(false);

const item = ref(props.item);
const token = ref(props.item?.token || '');
const name = ref(props.item?.name || '');
const saving = ref(false);

const save = async () => {
    saving.value = true;
    try {
        item.value.name = name.value;
        item.value.token = token.value;
        item.value = await $OrderTypeApiService.save(item.value);
        emit('saved', item.value);
        resetForm();
    } catch (error) {
        console.error('Error saving bonification type:', error);
    } finally {
        saving.value = false;
    }
}

const deleteOrderType = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    await $OrderTypeApiService.deleteOrderType(item.value.id);
    emit('deleted')
  }
}

const resetForm = () => {
  token.value = '';
  name.value = '';
};

watch(() => props.item, (newItem) => {
  if (newItem && newItem.id) { // is editing
    token.value = newItem.token;
    name.value = newItem.name;
  } else { // is creating
    resetForm();
  }
}, { immediate: true });

onMounted(async () => {
  objectPermissions.value = await checkPermission($OrderApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
});
</script>

<template>
    <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion }">
        <div class="flex justify-between">
        <H1Region v-if="item?.id" class="mb-3">{{ t('common.modify') }} {{ t('order_block.order_type') }}</H1Region>
        <H1Region v-if="!item?.id" class="mb-3">{{ t('order_block.new_order_type') }}</H1Region>
        </div>
        <form @submit.prevent="save">
            <div class="mb-2">
                <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
                <input type="text" v-model="token" class="input" id="token" name="token"/>
            </div>
            <div class="mb-2">
                <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
                <input type="text" v-model="name" class="input" />
            </div>
            <hr class="mb-2 col-span-3" />
            <div class="col-span-3 flex flex-row-reverse mt-4">
              <button v-if="item?.id" @click="deleteOrderType" class="button-default mx-5" type="button"> 
                &nbsp; {{ $t('common.delete') }}
              </button>
              <button type="submit" :disabled="saving" class="button-primary">
                <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
              </button>
            </div>
          </form>
    </div>
</template>