<!-- components/organisms/BonificationTypeRegion.vue -->
<script setup>
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import BonificationTypeEditRegion from '~/components/organisms/BonificationTypeEditRegion.vue';
import ConfigList from '~/components/organisms/ConfigList.vue';
import VariableTypeSelectMultiple from '~/components/organisms/VariableTypeSelectMultiple.vue';
import { VariableTypeDataTypeChoices, VariableTypeApplicationChoices } from '~/utils/variable-type';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-subregion', 'close']);
const router = useRouter();
const { $BonificationTypeApiService, $ContractApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const end_at = ref(null);
const variableTypeSelectedItems = ref([]);

// Funció per inicialitzar `variableTypeSelectedItems` basat en les dades
const initializeVariableTypeSelectedItems = () => {
  if (data.value && data.value.variable_types) {
    variableTypeSelectedItems.value = data.value.variable_types.map(v => v.id); // Ajusta segons la teva estructura de dades
  }
}

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $BonificationTypeApiService.getDetail(props.id);
    data.value = result;
    end_at.value = result.end_at;
    initializeVariableTypeSelectedItems();
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

// Watcher per sincronitzar canvis en `data`
watch(() => data.value, () => {
  initializeVariableTypeSelectedItems();
}, { immediate: true });

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  getData();
});

// Subregion
const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);

const closeSubRegion = () => {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const ChangeEndAt = (event) => {
  let saveData = {
    id: props.id,
    end_at: end_at.value
  }
  $BonificationTypeApiService.save(saveData)

}

const showSubRegion = () => {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const openEdit = () => {
  showRegionDetailComponent.value = 'BonificationTypeEditRegion';
  showSubRegion();
}

const openConfigDocuments = () => {
  showRegionDetailComponent.value = 'ConfigList';
  showSubRegion();
}

const openVariableTypeSelectMultiple = () => {
  showRegionDetailComponent.value = 'VariableTypeSelectMultiple';
  showSubRegion();
}

const deactivateBonificationType = async () => {
  if (confirm(`${t("confirmation_text_block.confirm_deactivate")}\n${t("warning_block.warning_irreversible")}`)) {

    let saveObject = {
      id: props.id,
      is_active: false
    }

    isSaving.value = true;
    try {
      await $BonificationTypeApiService.save(saveObject);
      await getData(); // Actualitzar les dades després de guardar
    } catch (err) {
      console.error('Error al guardar els tipus de variables:', err);
      // Opcional: Mostrar un missatge d'error a l'usuari
    } finally {
      isSaving.value = false;
    }
  }
}

const handleDocumentChanged = () => {
  getData();
}

const onSavedAdd = (item) => {
  getData();
  closeSubRegion();
}

// Watcher per detectar canvis en `variableTypeSelectedItems` i guardar-los
const isSaving = ref(false); // Flag per evitar bucles infinits

watch(variableTypeSelectedItems, async (newItems, oldItems) => {
  if (!objectPermissions.value.can_change) return;
  if (isSaving.value) return; // Evitar reaccions durant el guardat

  // Comprovar si hi ha canvis
  const areDifferent = JSON.stringify(newItems) !== JSON.stringify(oldItems);
  if (!areDifferent) return;

  isSaving.value = true;
  const saveObject = {
    id: props.id,
    variable_types_ids: newItems
  };

  try {
    await $BonificationTypeApiService.save(saveObject);
    await getData(); // Actualitzar les dades després de guardar
  } catch (err) {
    console.error('Error al guardar els tipus de variables:', err);
    // Opcional: Mostrar un missatge d'error a l'usuari
  } finally {
    isSaving.value = false;
  }
});
</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>{{t('common.error')}}: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          <span :class="{ 'line-through': !data.is_active }">
            {{ $t('contract_block.bonification_type') }}
          </span>
          <span v-if="!data.is_active" class=" mx-5 px-2 bg-red-100 text-red-500 text-sm">
            {{ t("common.deactivated") }}
          </span>

        </H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="$t('common.modify')" @click="openEdit"></DropdownOption>
          <DropdownOption :name="`${$t('common.modify')} ${$t('common.doc_type')}`" @click="openConfigDocuments"></DropdownOption>
          <DropdownOption :name="`${$t('common.modify')} ${$t('contract_block.variable_type')}`" @click="openVariableTypeSelectMultiple">
          </DropdownOption>
          <DropdownOption v-if="data.is_active" :name="`${$t('common.deactivate')} ${$t('contract_block.bonification_type')}`"
            @click="deactivateBonificationType"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel="id">
        <div class="mb-3 grid grid-cols-2 gap-4">
          <FieldDetail :label="t('common.name')" :strong="true" :value="data.name">
            <strong class="text-sky-500">{{ data.name }}</strong>
          </FieldDetail>
          <FieldDetail :label="t('common.identificator')" :value="data.token" />
        </div>

        <div class="mb-3 grid grid-cols-2 gap-4">
          <FieldDetail :label="t('common.start')" :value="formatDate(data.start_at)" class="mt-4" />

          <div class="flex justify-between">
            <span class="text-slate-400 mt-4">{{ t('common.end') }}</span>
            <AtomsInputDate :disabled="!objectPermissions?.can_change" v-model="end_at" class="mr-20 no-border" @change="ChangeEndAt($event)" />
          </div>

        </div>

        <div id="documents" class="mb-3">
          <p class="mb-3 font-semibold">{{ $t('common.doc_type') }}</p>
          <div class="pl-3 pr-3">
            <ul class="mb-2">
              <li v-for="docType in data.bonification_type_documentation_types" :key="docType.id">
                <span class="text-slate-900 p-1">
                  <Icon name="fa6-regular:file-lines" class="text-slate-500" /> &nbsp;
                  {{ docType.name }}
                  <em v-if="!docType.is_mandatory"> ({{ $t('common.optional') }})</em>
                </span>
              </li>
            </ul>
            <button v-if="data.bonification_type_documentation_types.length === 0 && objectPermissions?.can_change" @click="openConfigDocuments"
              class="underline text-sky-500 hover:no-underline">
              {{ $t('common.add') }} {{ $t('common.doc_type') }}
            </button>
            <span v-if="data.bonification_type_documentation_types.length === 0 && !objectPermissions?.can_change" class="text-slate-500">
              {{ $t('common.no_doc_type') }}
            </span>
          </div>
        </div>

        <div id="vars" class="mb-3">
          <p class="mb-3 font-semibold">{{ $t('contract_block.variable_types') }}</p>
          <div class="pl-3 pr-3">
            <ul class="border-t mb-2">
              <li class="grid grid-cols-[1fr,1fr,1fr] text-base border-b items-center bg-white"
                v-for="variable in data.variable_types" :key="variable.id">
                <span class="text-slate-900 p-1 border-l pl-3">
                  <Icon name="fa6-solid:gear" class="text-slate-500" /> &nbsp;
                  {{ variable.name }}
                </span>
                <span class="text-slate-900 p-1 border-l">
                  {{ variable.data_type ? VariableTypeDataTypeChoices[variable.data_type] : '-' }}
                </span>
                <span class="text-slate-900 p-1 border-l">
                  {{ variable.application ? VariableTypeApplicationChoices[variable.application] : '-' }}
                </span>
              </li>
            </ul>
            <button v-if="data.variable_types.length === 0 && objectPermissions?.can_change" @click="openVariableTypeSelectMultiple"
              class="underline text-sky-500 hover:no-underline">
              {{ $t('common.add') }} {{ $t('contract_block.variable_type') }}
            </button>
            <span v-if="data.variable_types.length === 0 && !objectPermissions?.can_change" class="text-slate-500">
              {{ $t('contract_block.no_variable_type') }}
            </span>
          </div>
        </div>
      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <BonificationTypeEditRegion v-if="showRegionDetailComponent === 'BonificationTypeEditRegion'" :item="data"
          :isSubRegionOpen="true" @saved="onSavedAdd" />
        <ConfigList v-if="showRegionDetailComponent === 'ConfigList'" :title="$t('common.doc_type') + ': ' + data.name"
          entity="contract/bonification-type-documentation-type" :hasColor="false" :hasMandatoryCheck="true"
          parent_entity="bonification_type" :parent_id="props.id" @changed="handleDocumentChanged" />
        <VariableTypeSelectMultiple v-if="showRegionDetailComponent === 'VariableTypeSelectMultiple'"
          v-model="variableTypeSelectedItems" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
