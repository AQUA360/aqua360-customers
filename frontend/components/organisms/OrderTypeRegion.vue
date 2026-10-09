<script setup>

import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import OrderTypeDetail from '../molecules/OrderTypeDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import OrderReasonSelectMultiple from '~/components/organisms/OrderReasonSelectMultiple.vue';
import OrderTypeEditRegion from '~/components/organisms/OrderTypeEditRegion.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $OrderTypeApiService, $OrderApiService } = useNuxtApp();

const props = defineProps({
  id: Number,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-subregion', 'deleted', 'saved', 'close']);

const pending = ref(true);
const error = ref(null);

const data = ref(null);
const orderReasonSelectedItems = ref([]);

// Funció per inicialitzar `orderReasonSelectedItems` basat en les dades
const initializeOrderReasonSelectedItems = () => {
  if (data.value && data.value.reasons) {
    orderReasonSelectedItems.value = data.value.reasons.map(v => v.id); // Ajusta segons la teva estructura de dades
  }
}

// Subregion
const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);

const getData = async () => {
    pending.value = true;
    error.value = null;
    try {
        const result = await $OrderTypeApiService.getDetail(props.id);
        data.value = result;
    } 
    catch (err) {
        error.value = err;
    } 
    finally {
        pending.value = false;
    }
}

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
}); 

watch(() => props.id, () => {
  getData();
});

const edit = function () {
  showRegionDetailComponent.value = 'OrderTypeEditRegion';
  showSubRegion();
}

const openOrderReasonSelectMultiple = () => {
  showRegionDetailComponent.value = 'OrderReasonSelectMultiple';
  showSubRegion();
}

const showSubRegion = () => {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const closeSubRegion = () => {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const onSavedAdd = (item) => {
  getData();
  closeSubRegion();
  emit('saved', item)
}

const onDeleted = (data) => {
  emit('deleted')
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

// Watcher per sincronitzar canvis en `data`
watch(() => data.value, () => {
  initializeOrderReasonSelectedItems();
}, { immediate: true });

// Watcher per detectar canvis en `variableTypeSelectedItems` i guardar-los
const isSaving = ref(false); // Flag per evitar bucles infinits

watch(orderReasonSelectedItems, async (newItems, oldItems) => {
  if (isSaving.value) return; // Evitar reaccions durant el guardat

  // Comprovar si hi ha canvis
  const areDifferent = JSON.stringify(newItems) !== JSON.stringify(oldItems);
  if (!areDifferent) return;

  isSaving.value = true;
  const saveObject = {
    id: props.id,
    order_reasons_ids: newItems
  };

  try {
    await $OrderTypeApiService.save(saveObject);
    await getData();
  } 
  catch (err) {
    console.error('Error:', err);
  } 
  finally {
    isSaving.value = false;
  }
});

onMounted(async () => {
  objectPermissions.value = await checkPermission($OrderApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  getData();
});

</script>

<template>
    <div class="region__content">
        <div v-if="pending">
            <AppLoading :text="$t('common.loading')" />
        </div>
        <div v-else-if="error">
            <p>Error: {{ error.message }}</p>
            <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again') }}</button></p>
        </div>
        <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
            <div class="flex justify-between relative">
                <H1Region class="mb-3">{{ $t('order_block.order_type') }}</H1Region>
                <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
                    <DropdownOption :name="`${t('common.modify')} ${t('order_block.order_type')}`" @click="edit"></DropdownOption>
                    <DropdownOption :name="`${t('common.modify')} ${t('order_block.reasons')}`" @click="openOrderReasonSelectMultiple"></DropdownOption>
                </OptionsDropdown>
            </div>
            <div v-if="data" id="item_data" :data-rel=id>
                <OrderTypeDetail :id="props.id" :data="data"/>
                <br>
                <div id="reasons" class="mb-3">
                    <p class="mb-3 font-semibold">{{ $t('order_block.reasons') }}</p>
                    <div class="pr-3"> 
                        <ul class="border-t mb-2">
                          <li v-for="reason in data.reasons" :key="reason.id" class="grid grid-cols-[200px,1fr] text-base border-b items-center bg-white">
                            <span class="text-slate-900 p-1 border-l pl-3">
                              {{ reason.token }}
                            </span>
                            <span class="text-slate-900 p-1 border-l">
                              {{ reason.name }}
                            </span>
                          </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        <div v-if="SubRegion" role="region" id="subregion"
            class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <OrderTypeEditRegion v-if="showRegionDetailComponent === 'OrderTypeEditRegion'" :item="data"
                  :isSubRegionOpen="true" @saved="onSavedAdd" @deleted="onDeleted"/>
                <OrderReasonSelectMultiple v-if="showRegionDetailComponent === 'OrderReasonSelectMultiple'"
                  v-model="orderReasonSelectedItems"/>
            </div>
        </div>
    </div>
</template> 