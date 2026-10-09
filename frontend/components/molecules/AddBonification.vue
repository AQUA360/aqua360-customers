<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import InputDocument from '~/components/atoms/InputDocument.vue';
import VariableEdit from '~/components/molecules/VariableEdit.vue';


const { t } = useI18n();
const { $BonificationTypeApiService, $BonificationApiService, $BonificationDocumentationApiService, $VariableApiService } = useNuxtApp();
const emit = defineEmits(['new-item']);

const props = defineProps({
  request: Object,
  contract: Object,
  contract_request: Object,
  selectedBonificationType: Object
});

const bonification = ref(null);

const optionsBonificationTypes = ref([])

const loading_bonification_types = ref(true);
const loading = ref(true);

const selectedBonificationType = ref("");
const bonificationType = ref(null);

const documents = ref({});
const variables = ref({});

const getData = async () => {
  loading.value = true;
  await getBonificationTypes();

  loading.value = false;
};

const getBonificationTypes = async () => {
  loading_bonification_types.value = true;
  const response = await $BonificationTypeApiService.getAll();
  optionsBonificationTypes.value = response.results.filter(bonification => bonification.is_active);
  loading_bonification_types.value = false;
};

// saving
const save = async () => {
  const token = bonification.value?.token || new Date().toISOString().replace(/\D/g, '').slice(0, 14); // YYYYMMDDHHMMSS
  let data_save = {
    token: token,
    bonification_type: selectedBonificationType.value.id,
    contract_request: props.contract_request?.id || props.request?.id || null,
    contract: bonification.value?.contract?.id || props.contract?.id || null,
  }

  const response = await $BonificationApiService.save(data_save)

  bonification.value = response;

  // Guardar documents
  for (const doc of documents.value) {
    if (doc.checked) {
      await $BonificationDocumentationApiService.save({
        bonification: bonification.value.id,
        type: doc.type.id,
        file: null // TODO: save file
      });
    }
  }

  // Guardar variables
  for (const variable of variables.value) {
    variable.bonification = bonification.value.id;
    const save_data = {
      contract_request: props.contract_request?.id || props.request?.id || null,
      contract: bonification.value?.contract?.id || props.contract?.id || null,
      bonification: bonification.value.id,
      type: variable.type.id,
      value: variable.value,
      name: variable.type.name,
      ...(variable.start_at && { start_at: variable.start_at }),
      ...(variable.end_at && { end_at: variable.end_at }),
    };

    await $VariableApiService.save(save_data);
  }

  emit('new-item', bonification.value);
}


onMounted(() => {
  getData()
});

watch(selectedBonificationType, (newVal) => {
  bonificationType.value = optionsBonificationTypes.value.find(item => item.id === newVal.id);

  // del type, assignem els documents i variables
  documents.value = [];
  bonificationType.value.bonification_type_documentation_types.forEach(docType => {
    documents.value.push({
      type: docType,
      file: null
    })
  }) // endforeach


  // del type, assignem les variables
  variables.value = []
  bonificationType.value.variable_types.forEach(variableType => {
    variables.value.push({
      bonification: bonification.value?.id || null,
      type: variableType,
      value: '',
      start_at: '',
      end_at: ''
    })
  }) // endforeach

});


const onDocumentChecked = (data) => {
  const doc = documents.value.find(doc => doc.type.token === data.type);
  doc.checked = data.checked;
};

const onDocumentUpdate = (data) => {
  const doc = documents.value.find(doc => doc.type.token === data.type);
  doc.file = data.file;
};

const onDocumentDelete = (data) => {
  const doc = documents.value.find(doc => doc.type.token === data.type);
  doc.file = null;
};

const onVariableUpdate = (data) => {
  const variable = variables.value.find(v => v.type.token === data.type);
  if (variable === undefined) {
    console.error('Variable not found', data);
    return;
  }

  variable.value = data.value;
  variable.start_at = data.start_at;
  variable.end_at = data.end_at;
};

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('contract_block.bonification') }}</H1>
    </div>
    <div class="row">
      <div class="field mb-3">
        <label for="BonificationType" class="inline-block mb-1 font-semibold">{{ $t('contract_block.bonification_type') }}:</label>
        <select id="BonificationType" v-model="selectedBonificationType" class="input">
          <option value="">-- {{ $t('contract_block.select_bonification_type') }}</option>
          <option v-for="type in optionsBonificationTypes" :key="type.id" :value="type">
            {{ type.name }}
          </option>
        </select>
      </div>
    </div><!-- end row -->


    <div v-if="bonificationType">

      <hr class="my-2" />

      <p class="font-semibold mb-2">{{ $t('common.documentation') }}</p>

      <div v-for="docType in bonificationType.bonification_type_documentation_types" :key="docType.id"
        class="field mb-3">
        <InputDocument :doc_type="docType" @document-checked="onDocumentChecked" @document-update="onDocumentUpdate"
          @document-delete="onDocumentDelete" />
      </div>

      <p class="font-semibold mb-2">{{ $t('variables') }}</p>

      <div v-for="variableType in bonificationType.variable_types" :key="variableType.id" class="field mb-3">
        <VariableEdit :type="variableType" :item="variables[variableType.id] || {}"
          @update-variable="onVariableUpdate" />
      </div>

    </div><!-- end if selected -->

    <hr class="my-2" />

    <div class="flex flex-row-reverse mt-4">
      <button @click="save" :disabled="!selectedBonificationType" class="button-success">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('contract_block.new_bonification') }}
      </button>
    </div>
  </div>
</template>