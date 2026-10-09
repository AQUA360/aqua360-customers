<script setup>
import { ref, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';

// Components atòmics importats
import AtomsInputText from '~/components/atoms/InputText.vue';
import AtomsInputNumber from '~/components/atoms/InputNumber.vue';
import AtomsInputCheckbox from '~/components/atoms/InputCheckbox.vue';
import AtomsInputDate from '~/components/atoms/InputDate.vue';
// Si necessites AtomsInputDateTime, descomenta la següent línia
// import AtomsInputDateTime from '~/components/atoms/InputDateTime.vue';

// Definició de les propietats que el component rep
const props = defineProps({
  type: {
    type: Object,
    required: true
  },
  // Pot arribar buit: el pare encara no ha carregat la variable que s'edita, o
  // s'està creant una variable nova que encara no té valors.
  item: {
    type: Object,
    default: () => ({})
  }
});

// Definició dels esdeveniments que el component pot emetre
const emit = defineEmits(['update-variable']);

// Gestió de les traduccions
const { t } = useI18n();

// Copia reactiva de l'item per evitar mutacions directes de les props
const localItem = ref({ 
  value: props.item?.value || '', 
  start_at: props.item?.start_at || '', 
  end_at: props.item?.end_at || '' 
});

// Watch per sincronitzar els canvis de les props amb la còpia local
watch(() => props.item, (newItem) => {
  localItem.value = { 
    value: newItem?.value || '', 
    start_at: newItem?.start_at || '', 
    end_at: newItem?.end_at || '' 
  };
});

// Computed per determinar quina entrada mostrar segons el data_type
const inputComponent = computed(() => {
  switch (props.type.data_type) {
    case 'bool':
      return null;
    case 'int':
      return AtomsInputNumber;
    case 'char':
      return AtomsInputText;
    case 'float':
      return AtomsInputNumber;
    // Si en algun moment necessites suportar 'datetime', descomenta les següents línies
    // case 'datetime':
    //   return AtomsInputDateTime;
    default:
      return AtomsInputText;
  }
});

const inputComponentLabel = computed(() => {
  switch (props.type.data_type) {
    case 'bool':
      return null;
    case 'int':
      return `${t('common.value')} (${t('pricing_block.whole_num')})`;
    case 'float':
      return `${t('common.value')} (${t('pricing_block.dec_num')})`;
    default:
      return `${t('common.value')} (${t('common.text')})`;
  }
});


// Funció per manejar els canvis en l'entrada del valor
const handleInputChange = (value) => {
  localItem.value.value = value;
  emit('update-variable', { 
    ...(props.item || {}), 
    type: props.type.token,
    value: localItem.value.value, 
    start_at: localItem.value.start_at, 
    end_at: localItem.value.end_at 
  });
};

// Funció per manejar els canvis en les dates (start_at, end_at)
const handleDateChange = (field, value) => {
  localItem.value[field] = value;
  emit('update-variable', { 
    ...(props.item || {}), 
    type: props.type.token,
    value: props.type.data_type === 'bool' ? "True" : localItem.value.value, 
    start_at: localItem.value.start_at, 
    end_at: localItem.value.end_at
  });
};

// Funció per manejar els canvis en el checkbox (per tipus 'bool')
const handleCheckboxChange = (checked) => {
  localItem.value.value = checked;
  emit('update-variable', { 
    ...(props.item || {}), 
    type: props.type.token,
    value: localItem.value.value, 
    start_at: localItem.value.start_at, 
    end_at: localItem.value.end_at 
  });
};
</script>
<template>
  <fieldset class="mb-6 border px-4 py-3 bg-sky-50 w-full rounded">
    <legend class="px-3 font-semibold bg-white shadow"><Icon name="fa6-solid:gear" class="mr-1" /> {{ type.name }}</legend>
    <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
      
      <!-- Valor-Input -->
      <div>
        <component
          :is="inputComponent"
          v-model="localItem.value"
          :label="inputComponentLabel"
          @update:modelValue="handleInputChange"
          class="mb-2"
        />
      </div>
      
      <!-- Start_at -->
      <div>
        <AtomsInputDate
          v-model="localItem.start_at"
          :label="t('common.start_date')"
          @update:modelValue="(val) => handleDateChange('start_at', val)"
          class="mb-2"
        />
      </div>
      
      <!-- End_at -->
      <div>
        <AtomsInputDate
          v-model="localItem.end_at"
          :label="t('common.end_date')"
          @update:modelValue="(val) => handleDateChange('end_at', val)"
          class="mb-2"
        />
      </div>
      
    </div>
  </fieldset>
</template>
