<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import debounce from 'lodash.debounce';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import _ from 'lodash';
const { t } = useI18n();
const { $RouteApiService } = useNuxtApp();

const props = defineProps({
  zone_id: Number
});

const emit = defineEmits(['new-zone']);

const token = ref('')
const name = ref('')

const attemptedSave = ref(false);
const saving = ref(false);


const save = async () => {
  if (isValid()) {
    saving.value = true;

    const selectedOptions = {
      name: name.value,
      token: token.value,
      
    };

    let zone = null;

    if (props.zone_id != null && props.zone_id > 0) {
      selectedOptions.id = props.zone_id;
      zone = await $RouteApiService.updateZone(selectedOptions);
    }
    else {
      zone = await $RouteApiService.createZone(selectedOptions);
    }
    finishAndClose(zone);
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}

const getData = () => {
  if (props.zone_id != null && props.zone_id > 0) {
    $RouteApiService.getZone(props.zone_id).then((zone) => {
      token.value = zone.token;
      name.value = zone.name;
    })
    .catch((error) => {
      console.error(error);
    });
  }
  else {
    name.value = '';
    token.value = _.random(100000, 999999);
  }
}

const finishAndClose = (company) => {
  saving.value = false;
  emit('new-zone', company);
}

const isValid = () => {
  if (name.value == '') return false;
  if (token.value == '') return false;
  return true;
}

onMounted(() => {
  getData()
});

watch(() => props.zone_id, (newValue) => {
  getData();
});

</script>

<template>
  <div class="region__content">
    <div>
      <div class="flex justify-between items-center mb-2">
        <H1>{{ props.zone_id > 0 ? `${$t('common.modify')} ${t('service_block.zone')}` : $t('service_block.new_zone') }}</H1>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.code') }}</label>
          <input type="text" v-model="token" class="input" :class="{'invalid': attemptedSave && token == ''}"/>
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }} *</label>
          <input required type="text" v-model="name" :class="{'invalid': attemptedSave && name == ''}" class="input" />
        </div>
      </div>
      <hr/>
      <div class="flex flex-row-reverse mt-4">
        <button @click="save"  :disabled="saving" class="button-primary"><Icon name="fa6-solid:floppy-disk"/>&nbsp; {{ $t('common.save') }}</button>
      </div><!-- end contingut botons -->
    </div>
  </div><!-- end wrapper -->
</template>