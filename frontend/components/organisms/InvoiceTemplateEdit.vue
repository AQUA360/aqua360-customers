<script setup>
// components/organisms/ContractRequestTypeRegion.vue
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import { MessageTypeChoices } from '~/utils/messages';
import MessagesConditionForm from '../molecules/MessagesConditionForm.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  id: Number,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
});

const emit = defineEmits(['show-subregion', 'changed', 'close']);
const router = useRouter();
const { $InvoiceTemplateApiService, $InvoiceApiService, $ProductApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const token = ref(null);
const name = ref(null);
const origin = ref(null)
const color = ref(null)

const origins = ref([])

const getData = async () => {
  pending.value = true;
  error.value = null;
  console.log(props.id)
  if (props.id) {
    try {
      const result = await $InvoiceTemplateApiService.getDetail(props.id);
      token.value = result.token;
      name.value = result.name;
      origin.value = origins.value.find(item => item.code == result.origin.id);
      color.value = result.color;

    } catch (err) {
      error.value = err;
    } finally {
      pending.value = false;
    }
  }
  pending.value = false

}

const getOrigins = async () => {
  try {
    const result = await $ProductApiService.getOrigins();
    result.results.forEach(item => {
      origins.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.log(error);
  }
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'origin':
      origin.value = event;
      break;
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

}, { immediate: true });

onMounted(async () => {
  objectPermissions.value = await checkPermission($InvoiceApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  getOrigins()
  getData();
});

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null)

const showDetail = (component, id) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id
  showSubRegion();
}

const closeSubRegion = () => {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null
  //emit('show-subregion', false);
}

const showSubRegion = () => {
  SubRegion.value = true;
  //emit('show-subregion', true);
}


const isSaving = ref(false);

const save = async () => {
  isSaving.value = true;

  if (!isValid()) {
    toast.error(t('warning_block.data_warning'));
    isSaving.value = false;
    return;
  }

  let saveData = {
    id: props.id ? props.id : null,
    token: token.value,
    name: name.value,
    origin_id: origin.value.code,
  }

  let result = await $InvoiceTemplateApiService.save(saveData);
  emit('changed', result);
  isSaving.value = false;

}

const isValid = () => {
  if (token.value == '' || token.value == null) return false;
  if (name.value == '' || name.value == null) return false;
  if (origin.value == null) return false;
  return true;
}


</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[47%]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ props.id ? `${$t('common.modify')} ${t('common.template')}` 
          : $t('common.new_template') }}
        </H1Region>
        
      </div>

      <div id="item_data" :data-rel="id">
        <div class="row grid grid-cols-2 gap-3">
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identification') }}</label>
            <input type="text" v-model="token" class="input"
              :class="{ 'invalid': isSaving && (token == '' || token == null) }" />
          </div>
          <div v-if="props.id" class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.color') }}</label>
            <AtomsColorPicker :entity="'billing/invoice-template'" :id="props.id" :code="color"/>
          </div>
          
        </div>

        <div class="row grid grid-cols-2 gap-3">
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
            <input type="text" v-model="name" class="input"
              :class="{ 'invalid': isSaving && (name == '' || name == null) }" />
          </div>
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.origin') }}</label>
            <v-select class="block w-full mr-1 required" :model-value="origin"
              @update:modelValue="updateSelect($event, 'origin')" :options="origins" />
          </div>
        </div>

        <hr class="my-2" />

        <div class="col-span-2 flex flex-row-reverse mt-4">
          <button @click="save" class="button-primary">
            <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
              $t('common.save') }}
          </button>
        </div>

      </div>


    </div><!-- end if pending -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10 w-[47%] overflow-y-auto overflow-x-hidden"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }" >
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- SUBREGIONS -->
      </div>
    </div>
  </div><!-- end region__content -->
</template>
