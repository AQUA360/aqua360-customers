<script setup>
// components/organisms/ContractRequestTypeRegion.vue
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import { MessageTypeChoices } from '~/utils/messages';
import MessagesConditionForm from '../molecules/MessagesConditionForm.vue';
import toast from '~/plugins/npm/toast';

const { t } = useI18n();

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
  invoice: Object
});

const emit = defineEmits(['show-subregion', 'changed']);
const router = useRouter();
const { $InvoiceTemplateApiService, $MessageApiService, $InvoiceApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const invoice_template_data = ref(null)
const invoices = ref([])

const title = ref(null);
const content = ref(null);
const type = ref(null)
const conditions = ref([])
const date_start = ref(null)
const date_end = ref(null)

const condition_to_edit = ref(null)

const messageTypes = ref([]);

const messages = ref([]);

const getData = async () => {
  pending.value = true;
  error.value = null;
  invoice_template_data.value = props.invoice ? props.invoice : null
  if (props.id) {
    try {
      const result = await $MessageApiService.getDetail(props.id);
      title.value = result.title;
      content.value = result.content;
      type.value = messageTypes.value.find(item => item.value == result.message_type);
      conditions.value = result.conditions? result.conditions:[];
      invoices.value = result.invoices;
      date_start.value = result.start_at;
      date_end.value = result.end_at;


      //getInvoices()
    } catch (err) {
      error.value = err;
    } finally {
      pending.value = false;
    }
  }
  pending.value = false

}

const getMessageTypes = async () => {
  messageTypes.value = [];
  messageTypes.value = Object.keys(MessageTypeChoices).map(key => ({
    value: key,
    label: MessageTypeChoices[key]
  }))
}

/* const getInvoices = async () => {
  console.log("getInvoices")
  console.log(conditions.value)
  console.log(invoice_template_data.value)
  if (conditions?.value?.length == 0 || !conditions.value) {
    console.log("no conditions")
    invoices.value = [];
    const result = await $InvoiceApiService.getAll('', [], 1, null, false, null, true, invoice_template_data.value.origin.id);
    console.log(result)
    invoices.value = result.results;
  }
} */

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

onMounted(() => {
  getMessageTypes()
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
  condition_to_edit.value = null
  //emit('show-subregion', false);
}

const showSubRegion = () => {
  SubRegion.value = true;
  //emit('show-subregion', true);
}

const changeCondition = (condition) => {
  conditions.value.push(condition)
  closeSubRegion()
}

const deleteCondition = (condition) => {
  let condition_index = conditions.value.findIndex(c => c.name == condition.name && c.formula == condition.formula);
  if (condition_index > -1) {
    conditions.value.splice(condition_index, 1);
  }
  //if condition has id, delete it
  /* if(condition.id){
    $MessageApiService.deleteCondition(condition.id)
  } */
}

const editCondition = (condition) => {
  condition_to_edit.value = condition
  showDetail('ConditionRegion')
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'msg_type':
      type.value = event;
      break;
  }
}

const isSaving = ref(false);

const save = async () => {
  isSaving.value = true;

  if (!isValid()) {
    toast.error(t('warning_block.data_warning'));
    isSaving.value = false;
    return;
  }
  const condition_ids = []
  if(conditions.value && conditions.value.length > 0){
    for(let condition of conditions.value){
      let conditionData = {
        id: condition.id? condition.id:null,
        name: condition.name,
        quantity: condition.quantity,
        operation: condition.operation,
        formula: condition.formula,
      }
      let savedCondition = await $MessageApiService.saveCondition(conditionData)
      condition_ids.push(savedCondition.id)
    }
  }

  let saveData = {
    id: props.id ? props.id : null,
    title: title.value,
    content: content.value,
    message_type: type.value.value,
    template: invoice_template_data.value.id,
    start_at: date_start.value? date_start.value:null,
    end_at: date_end.value? date_end.value:null,
    condition_ids: condition_ids,
  }

  let result = await $MessageApiService.save(saveData);
  emit('changed', result);
  isSaving.value = false;

}

const isValid = () => {
  if (title.value == '' || title.value == null) return false;
  if (type.value == null) return false;
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
          {{ props.id ? `${$t('common.modify')} ${$t('common.message')}` : $t('common.new_message') }}
        </H1Region>

        <div class="mb-3">
          <AtomsColorBadge v-if="invoice_template_data" :value="invoice_template_data.name" :color="''"
            class="mx-2 opacity-75 font-semibold"></AtomsColorBadge>
        </div>
      </div>

      <div id="item_data" :data-rel="id">
        <div class="row grid grid-cols-2 gap-3">
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.title') }}</label>
            <input type="text" v-model="title" class="input"
              :class="{ 'invalid': isSaving && (title == '' || title == null) }" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.type') }}</label>
            <v-select class="block w-full mr-1 required" :model-value="type"
              @update:modelValue="updateSelect($event, 'msg_type')" :options="messageTypes" />
          </div>
        </div>
        <div class="row grid grid-cols-2 gap-3">
          <div>
            <span class="text-gray-500 font-medium">{{ $t('common.from') }}</span>
            <AtomsInputDate v-model="date_start" class="w-full" @update:modelValue="updateSelect($event, 'start_at')" />
          </div>
          <div>
            <span class="text-gray-500 font-medium">{{ $t('common.to') }}</span>
            <AtomsInputDate v-model="date_end" class="w-full" @update:modelValue="updateSelect($event, 'end_at')" />
          </div>
        </div>

        <hr class="my-2" />

        <div>
          <label for="content" class="block font-medium text-slate-500 mb-2">{{ t('common.conditionals') }}</label>

          <div class="row grid grid-cols-2 gap-3 mt-2">
            <div class="border rounded-lg py-2 px-4 border-slate-300 shadow-sm w-full bg-slate-100">
              <div v-if="conditions && conditions.length > 0" class="text-center">
                <div v-for="condition in conditions" :key="condition.id" class="">
                  <span class="text-[11px] text-slate-500 font-semibold italic my-1 flex items-center flex justify-between">
                    <span>
                      {{ condition.name }}
                    </span>
                    <div>
                      <button @click="editCondition(condition)" class="mx-1 border border-slate-300 rounded-md py-1 px-2 hover:bg-white">
                        <Icon name="fa6-solid:pencil" class="text-slate-500" />
                      </button>
                      <button @click="deleteCondition(condition)" class="mx-1 border border-slate-300 rounded-md py-1 px-2 hover:bg-white">
                        <Icon name="fa6-solid:trash" class="text-slate-500" />
                      </button>
                    </div>
                  </span>
                </div>
              </div>
              <div v-else>
                <span class="text-[11px] text-slate-500 font-semibold italic my-1 flex items-center">
                  <Icon name="fa6-solid:circle-exclamation" class="text-slate-500 mr-1" />
                  <p>
                    {{ t('common.no_records') }}
                  </p>
                </span>
              </div>
            </div>
            
            <div class="h-[40px]">
              <button class="button-default flex gap-3 items-center mb-2" @click="showDetail('ConditionRegion')">
                {{ t('common.add') }} {{ t('pricing_block.conditions') }}
                <Icon name="fa6-solid:plus" class="text-slate-500" />
              </button>
            </div>
          </div>
        </div>

        <!-- <div class="row grid grid-cols-2 gap-3 mt-2">
          <div class="p-2 w-full text-slate-500 font-semibold">
            <span>
              {{ t('Factures afectades: ') }}
              {{ invoices ? invoices.length : 0 }}
            </span>
          </div>
        </div> -->

        <hr class="my-2" />

        <div class="row">
          <label for="content" class="block text-sm font-medium text-slate-500 mb-2">{{ t('customer_service_block.body') }}</label>
          <textarea name="content" id="content" cols="30" rows="5" v-model="content"
            class="w-full border rounded-lg p-2">

          </textarea>

        </div>

        <div class="col-span-2 flex flex-row-reverse mt-4">
          <button @click="save" :disabled="isSaving" class="button-primary">
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
        <MessagesConditionForm v-if="showRegionDetailComponent === 'ConditionRegion'" 
        :condition="condition_to_edit" @save="changeCondition" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
