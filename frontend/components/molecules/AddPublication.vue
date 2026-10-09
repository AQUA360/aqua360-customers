<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import debounce from 'lodash.debounce';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import _ from 'lodash';
const { t } = useI18n();
const { $PublicationApiService } = useNuxtApp();

const props = defineProps({
  id: {
    type: Number,
    default: null
  },
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['new-publication']);

const isEditing = computed(() => props.id != null);

const token = ref('')
const name = ref('')
const boeNumber = ref(null)
const boeDate = ref(null)
const reference = ref('')
const content = ref(null)
const amount = ref(null)

const SubRegion = ref(props.isSubRegionOpen);

const attemptedSave = ref(false);
const saving = ref(false);


const save = async () => {
  if (isValid()) {
    saving.value = true;

    const selectedOptions = {
      id: props.id ?? undefined,
      name: name.value,
      boe_number: boeNumber?.value || null,
      boe_date: boeDate?.value,
      reference: reference?.value || null,
      content: content?.value,
    };

    let br = null;
    br = await $PublicationApiService.save(selectedOptions);

    finishAndClose(br);
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}

const getData = async () => {
  if (props.id != null) {
    const response = await $PublicationApiService.getDetail(props.id);
    token.value = response.token ?? '';
    name.value = response.name ?? '';
    boeNumber.value = response.boe_number ?? null;
    boeDate.value = response.boe_date ?? null;
    reference.value = response.reference ?? '';
    content.value = response.content ?? null;
  }
  else {
    name.value = '';
  }
}


const finishAndClose = (br) => {
  saving.value = false;
  emit('new-publication', br);
}

const isValid = () => {
  if (name.value == '') return false;
  if (!boeDate.value) return false;
  //if (!reference.value) return false;

  return true;
}

onMounted(() => {
  getData()
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
  getData();
});

watch(() => props.id, () => {
  getData();
});

</script>

<template>
  <div class="region__content" >
    <div>
        <H1>{{ isEditing ? $t('pricing_block.edit_publication') : $t('pricing_block.new_publication') }}</H1>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }} *</label>
          <input required type="text" v-model="name" :class="{ 'invalid': attemptedSave && name == '' }" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.boe') }}</label>
          <input required type="text" v-model="boeNumber" class="input" />
        </div>
        <div class="mb-2">
          <AtomsInputDate v-model="boeDate" :label="t('common.date')" class="mb-2" :required="true" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.reference') }} *</label>
          <input required type="text" v-model="reference" :class="{ 'invalid': attemptedSave && reference == '' }"
            class="input" />
        </div>
      </div>
      <div class="row">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.description') }}</label>
          <input required type="text" v-model="content" 
            class="input" />
        </div>
      </div>
      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->
      
    </div>
  </div><!-- end wrapper -->
</template>