<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import VariableEdit from '~/components/molecules/VariableEdit.vue';
import { useStandaloneVariableTypes } from '~/composables/useStandaloneVariableTypes';


const { t } = useI18n();
const { $VariableApiService, $VariableTypeApiService } = useNuxtApp();
const emit = defineEmits(['new-item']);

const props = defineProps({
  contract: Object,
  contract_request: Object,
  selectedVariableType: Object,
  variable: Object,
  multiple: {
    type: Boolean,
    default: false
  }
});

const variable = ref(null);

const optionsVariableTypes = ref([])

const loading_variable_types = ref(true);
const loading = ref(true);

const selectedVariableType = ref("");
const variableType = ref(null);

const getData = async () => {
  loading.value = true;
  selectedVariableType.value = null
  variableType.value = null
  variable.value = null
  await getVariableTypes();
  if (props.variable !== null && props.variable != undefined) {
    // Primer la variable i després el tipus: el `watch` de `selectedVariableType`
    // pinta el formulari, i si encara no hi hagués variable rebria `item = null`.
    variable.value = { ...props.variable };
    selectedVariableType.value = optionsVariableTypes.value.find(item => item.id === props.variable?.type) || null;
    variableType.value = await $VariableTypeApiService.getDetail(props.variable.type);
  }

  loading.value = false;
};

const { standaloneVariableTypes, fetchStandaloneVariableTypes } = useStandaloneVariableTypes();

const getVariableTypes = async () => {
  loading_variable_types.value = true;
  if (props.variable) {
    // Editant una variable existent (també les d'una bonificació) el tipus no es pot
    // canviar: només cal tenir-lo a la llista per mostrar-lo.
    const response = await $VariableTypeApiService.getAllUnpaginated();
    optionsVariableTypes.value = response.filter(variable => variable.is_active || variable.id === (props.variable.type?.id ?? props.variable.type));
  } else {
    // Una variable nova només pot ser personalitzada: les que formen part d'una
    // bonificació s'afegeixen des de la bonificació.
    await fetchStandaloneVariableTypes();
    optionsVariableTypes.value = standaloneVariableTypes.value;
  }
  loading_variable_types.value = false;
};

// saving
const save = async () => {
  if(!props.multiple){
    // En edició, `variable.type` pot ser l'id que ve de l'API o l'objecte sencer que
    // posa el selector de tipus; el tipus triat (`variableType`) sempre és l'objecte.
    const type = variableType.value || variable.value.type;

    const save_data = {
      // El desat d'una variable existent és un PUT: tot el que no s'enviï es buida.
      // Cal arrossegar els vincles que no es toquen des del formulari (la bonificació
      // d'on penja la variable, el token) o es perdrien en editar-la.
      ...(props.variable || {}),
      id: props.variable?.id || null,
      contract_request: props.contract_request?.id || props.variable?.contract_request || null,
      contract: props.contract?.id || props.variable?.contract || null,
      type: type?.id || type,
      value: variable.value.value,
      name: type?.name || variable.value.name,
      start_at: variable.value.start_at || null,
      end_at: variable.value.end_at || null,
    };

    await $VariableApiService.save(save_data);
  }else{
    //?
  }

  emit('new-item', variable.value);
}


// La càrrega la dispara el watch de `props.variable` (immediate), no cal repetir-la
// aquí: dues `getData()` concurrents es trepitjaven el `variable` que s'està editant.

watch(selectedVariableType, (newVal) => {
  if (newVal !== null) {
    variableType.value = optionsVariableTypes.value.find(item => item.id === newVal.id);

    // Editant una variable existent, el selector el fixa `getData()` amb el tipus que
    // ja té: no és un canvi de tipus de l'usuari i no s'ha de buidar el valor desat.
    if (props.variable && (props.variable.type?.id ?? props.variable.type) === newVal.id) return;

    variable.value = {
      type: variableType.value,
      value: null,
      start_at: null,
      end_at: null,
    }
  }
  
});

watch(() => props.variable, (newVal) => {
  if (props.variable) {
    variable.value = { ...newVal };
  }
  getData()
}, { immediate: true });


const onVariableUpdate = (data) => {
  variable.value.value = data.value;
  variable.value.start_at = data.start_at;
  variable.value.end_at = data.end_at;
};

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('pricing_block.variable') }}</H1>
    </div>
    <div v-if="!props.variable && !loading_variable_types && optionsVariableTypes.length === 0"
      class="bg-sky-100 text-sky-700 py-3 px-5 rounded-lg mb-3">
      {{ $t('contract_block.no_standalone_variable_types') }}
    </div>
    <div v-else class="row">
      <p v-if="!props.variable" class="text-sm text-slate-500 mb-2">{{ $t('contract_block.standalone_variable_types_info') }}</p>
      <div class="field mb-3">
        <label for="VariableType" class="inline-block mb-1 font-semibold">{{ $t('contract_block.variable_type') }}:</label>
        <select id="VariableType" v-model="selectedVariableType" class="input" :disabled="props.variable">
          <option value="">-- {{ $t('contract_block.select_variable_type') }}</option>
          <option v-for="type in optionsVariableTypes" :key="type.id" :value="type">
            {{ type.name }} &nbsp; &nbsp; ({{ type.data_type }}) #{{ type.token }}
          </option>
        </select>
      </div>
    </div><!-- end row -->


    <div v-if="variableType && variable">
      <VariableEdit :type="variableType" :item="variable" @update-variable="onVariableUpdate" />
    </div>

    <hr class="my-2" />

    <div class="flex flex-row-reverse mt-4">
      <button v-if="props.variable || optionsVariableTypes.length > 0" @click="save" :disabled="!selectedVariableType" class="button-success">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
      </button>
    </div>
  </div>
</template>