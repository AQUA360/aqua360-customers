<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';

import H1 from '~/components/atoms/H1.vue';

const { t } = useI18n();
const { $ACADocumentApiService } = useNuxtApp();

const file = ref(null)

const emit = defineEmits(['on-processed'])

const handleDocumentUpdate = (f) => {
  file.value = f;
}

const save = async () => {

  let data = {
    token: _.random(10000, 99999),
    file: file.value
  };

  await $ACADocumentApiService.save(data)

  emit('on-processed')
};

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('common.aca_doc_upload') }}</H1>
    </div>

    <AtomsInputFile @update="handleDocumentUpdate" />

    <div class="col-span-3 flex flex-row-reverse mt-4">
      <button @click="save" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
      </button>
    </div>
  </div>
</template>
