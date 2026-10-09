<script setup>
// components/organisms/ContractRequestTypeRegion.vue
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import ConfigList from '~/components/organisms/ConfigList.vue';
import MessageEdit from './MessageEdit.vue';
import MessageRegion from './MessageRegion.vue';
import InvoiceTemplateEdit from './InvoiceTemplateEdit.vue';

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

const emit = defineEmits(['show-subregion', 'changed', 'close']);
const router = useRouter();
const { $InvoiceTemplateApiService, $MessageApiService, $InvoiceApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const messages = ref([]);
const variableTypeSelectedItems = ref([]);

// Funció per inicialitzar `variableTypeSelectedItems` basat en les dades
const initializeVariableTypeSelectedItems = () => {
  if (data.value && data.value.variable_types) {
    variableTypeSelectedItems.value = data.value.variable_types.map(v => v.id);
  }
}


const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $InvoiceTemplateApiService.getDetail(props.id);
    data.value = result;
    getMessages()
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const getMessages = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $MessageApiService.getAll('', [], 1, null, false, props.id);
    messages.value = result.results;
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
watch(() => data.value, (newValue) => {
  data.value = newValue;
}, { immediate: true, deep: true });

onMounted(async () => {
  objectPermissions.value = await checkPermission($InvoiceApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  getData();
});

// Subregion
const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const closeSubRegion = () => {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null
  emit('show-subregion', false);
}

const showDetail = (component, id) => {
  closeSubRegion()
  showRegionDetailComponent.value = component;
  regionDetailId.value = id ? id : null
  showSubRegion()
}

const templateChange = () => {
  console.log(props.id)
  router.push(`/billing/invoice-templates/edit/${props.id}`)
}

const showSubRegion = () => {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const openEdit = () => {
  showRegionDetailComponent.value = 'ContractRequestTypeEditRegion';
  showSubRegion();
}

const ChangedMessage = (message) => {
  getData()
  closeSubRegion();
  emit('changed');
}

const updateRegion = () => {
  getData();
  closeSubRegion();
  emit('changed')
}

const handleDocumentChanged = () => {
  console.log('handleDocumentChanged');
  getData();
  emit('changed');
}

// Watcher per detectar canvis en `variableTypeSelectedItems` i guardar-los
const isSaving = ref(false); // Flag per evitar bucles infinits

watch(variableTypeSelectedItems, async (newItems, oldItems) => {
  if (isSaving.value) return; // Evitar reaccions durant el guardat

  // Comprovar si hi ha canvis
  const areDifferent = JSON.stringify(newItems) !== JSON.stringify(oldItems);
  if (!areDifferent) return;

  isSaving.value = true;

  try {

  } catch (err) {
    console.error('Error al guardar els tipus de variables:', err);
    // Opcional: Mostrar un missatge d'error a l'usuari
  } finally {
    isSaving.value = false;
  }

  emit('changed');
});


</script>

<template>
  <div v-if="objectPermissions?.can_view" class="region__content">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('common.template') }}
        </H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="$t('common.modify')" @click="showDetail('InvoiceTemplateEdit', data.id)">
            <Icon name="fa6-solid:pencil" class="display-inline mr-2" /> {{ $t('common.modify') }}
          </DropdownOption>
          <DropdownOption :name="$t('common.show')" >
            <Icon name="fa6-solid:eye" class="display-inline mr-2" /> {{ $t('common.show') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.modify')} ${t('common.template')}`" @click="templateChange">
            <Icon name="fa6-solid:address-card" class="display-inline mr-2" /> {{ t('common.modify') }} {{ t('common.template') }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel="id">
        <div class="mb-3 grid grid-cols-2 gap-4">
          <FieldDetail :label="$t('common.name')" :strong="true" :value="data.name">
            <strong class="text-sky-500">{{ data.name }}</strong>
          </FieldDetail>
          <FieldDetail :label="$t('common.origin')" :strong="true" :value="data.name">
            <AtomsColorBadge :value="data.origin?.name" :color="data.color">
            </AtomsColorBadge>
          </FieldDetail>
        </div>
      </div>

      <hr class="my-2" />

      <div>
        <fieldset>
          <div class="flex justify-between items-center">
            <legend class="mb-3 font-semibold py-2 text-slate-700">
              {{ $t('billing_block.associated_messages') }}
            </legend>
            <button v-if="objectPermissions?.can_change" class="px-2 text-sm flex gap-3 items-center mb-3 hover:bg-slate-100"
              @click="showDetail('MessageEdit', null)">
              <Icon name="fa6-solid:plus" class="text-slate-500" />
              {{ $t('common.add') }} {{ $t('common.message') }}
            </button>
          </div>
          <div v-if="messages && messages.length>0" class="grid grid-cols-2 gap-3 mt-2">
            <div v-for="item in messages" :key="item.id"
              class="mb-3 border border-gray-300 rounded-lg customers-shadow p-4 bg-white">
              <div class="flex items-center grid grid-rows-2">
                <div class="flex gap-2 py-2 mr-2 ">
                  <button v-if="objectPermissions?.can_change" @click="showDetail('MessageEdit', item.id)"
                    class="border p-1 text-sm bg-white right-3 top-3 rounded-lg text-slate-600 hover:bg-slate-200">
                    <Icon name="fa6-solid:pencil" />
                  </button>
                  <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                    @click="showDetail('MessageRegion', item.id)">
                    <abbr :title="item.id" class="no-underline">{{ item.title }}</abbr>
                  </button>
                </div>
                <div class="px-1 text-right text-sm text-slate-500">{{ item.content }}</div>
              </div>
              <!-- <div class="p-1 flex justify-end text-xs text-slate-500 font-semibold">
                {{ t('Factures afectades: ') }}
                {{ item.invoices ? item.invoices.length : 0 }}</div> -->
            </div>
          </div>
          <div v-else class="text-center bg-yellow-50 border border-gray-300 rounded-md py-4 mx-4 text-sm">
            <p class="text-center">{{ $t('common.no_records') }}</p>
          </div>
        </fieldset>
      </div>

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
        <ConfigList v-if="showRegionDetailComponent === 'ConfigList'" :title="$t('common.doc_types') + ': ' + data.name"
          entity="contract/contract-request-documentation-type" :hasColor="false" :hasMandatoryCheck="true"
          parent_entity="contract_request_type" :parent_id="props.id" @changed="handleDocumentChanged" />
        <MessageRegion v-if="showRegionDetailComponent === 'MessageRegion'" :id="regionDetailId" :invoice="data" />
        <MessageEdit v-if="showRegionDetailComponent === 'MessageEdit'" :id="regionDetailId" :invoice="data"
          @changed="ChangedMessage" />
        <InvoiceTemplateEdit v-if="showRegionDetailComponent === 'InvoiceTemplateEdit'" :id="regionDetailId"
          :invoice="data" @changed="updateRegion" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
