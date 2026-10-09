<script setup>
import H1 from '~/components/atoms/H1.vue';

const { t } = useI18n();
const { $OrderTypeApiService } = useNuxtApp();

const props = defineProps({
  isSubRegionOpen: Boolean,
  order_type_id: Number
});

const token = ref('')
const name = ref('')

const attemptedSave = ref(false);
const openSubRegion = ref(props.isSubRegionOpen);
const saving = ref(false);

const isValid = () => {
  return token.value != '' && name.value != '';
}

const save = async () => {
  if (isValid()) {
    saving.value = true;

    const selectedOptions = {
      token: token.value,
      name: name.value
    };
    let order_type = null
    if (props.order_type_id != null && props.order_type_id > 0) {
      //TODO: update
    }
    else {
      order_type = await $OrderTypeApiService.createOrderType(selectedOptions);
    }
    finishAndClose(order_type);
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}

const getData = () => {

}

const deleteOrderType = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    await $OrderTypeApiService.deleteOrderType(props.id);
    return navigateTo('/order/order-types/')
  }
}

const finishAndClose = (order_type) => {
  if (props.isSubRegionOpen.value) {
    saving.value = false;
    emit('new-order-type', order_type);
  }
  else{
    return navigateTo('/order/order-types/')
  }
}

onMounted(() => {
  getData()
});

</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': openSubRegion && isSubRegionOpen }">
    <div :class="{ 'pr-5': openSubRegion }">
      <div class="flex justify-between items-center mb-2">
        <H1>{{ props.order_type_id > 0 ? `${$t('common.modify')} ${t('order_block.order_type')}` : $t('order_block.new_order_type') }}</H1>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identification') }} *</label>
          <input required type="text" v-model="token" :class="{ 'invalid': attemptedSave && token == '' }" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }} *</label>
          <input required type="text" v-model="name" :class="{ 'invalid': attemptedSave && name == '' }" class="input" />
        </div>
      </div>
      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button v-if="props.order_type_id != null" @click="deleteOrderType" class="button-default mx-5">
          &nbsp; {{ $t('common.delete') }}
        </button>
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->
    </div>
  </div>
</template>