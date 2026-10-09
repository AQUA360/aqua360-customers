<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';

const { t } = useI18n();
const { $TankApiService } = useNuxtApp();
const emits = defineEmits(['saved']);

const props = defineProps({
  id: {
    type: Number,
    required: false,
  }
});

const inputToken = ref(null);
const inputName = ref(null);
const inputVolume = ref(0);
const inputCodeGis = ref(null);


const save = async () => {
  const data = {
    token: inputToken.value,
    name: inputName.value,
    volume: inputVolume.value,
    code_gis: inputCodeGis.value
  };

  if (props.id) {
    data.id = props.id;
  }

  const response = await $TankApiService.save(data);
  if (response) {
    emits('saved', response);
  }
};


onMounted(async () => {
  if (props.id) {
    const response = await $TankApiService.getDetail(props.id);
    if (response) {
      inputToken.value = response.token;
      inputName.value = response.name;
      inputVolume.value = response.volume || 0;
      inputCodeGis.value = response.code_gis;
    }
  }
});

</script>

<template>
  <div>
    <h2 class="text-xl font-semibold mb-4">{{ t('service_block.tank') }}</h2>
    <div class="row grid grid-cols-2 gap-3">
      <div class="mb-4">
        <label for="inputToken" class="block text-sm font-medium text-gray-700">{{ t('common.identification') }}</label>
        <input v-model="inputToken" type="text" id="inputToken" name="inputToken"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>
      <div class="mb-4">
        <label for="inputName" class="block text-sm font-medium text-gray-700">{{ t('common.name') }}</label>
        <input v-model="inputName" type="text" id="inputName" name="inputName"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>

      <div class="mb-4">
        <label for="inputVolume" class="block text-sm font-medium text-gray-700">{{ t('service_block.volume') }}</label>
        <div class="flex items-stretch">
          <input v-model="inputVolume" v-numeric-only id="inputVolume" name="inputVolume"
            class="block w-full py-2 px-3 border-y border-l border-gray-300 bg-white rounded-l-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
          <span class="px-3 bg-slate-200 rounded-r leading-8 border-gray-300 border-y border-r">m<sup>3</sup></span>
        </div>
      </div>
      <div class="mb-4">
        <label for="inputCodeGis" class="block text-sm font-medium text-gray-700">{{ t('service_block.gis_code') }}</label>
        <input v-model="inputCodeGis" type="text" id="inputCodeGis" name="inputCodeGis"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>
    </div>

    <hr class="mb-3" />

    <button @click="save" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
      <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
    </button>
  </div>
</template>
