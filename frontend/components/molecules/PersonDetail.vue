<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';

const { $PersonApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  data: {
    type: Object,
    required: false
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
});

const emit = defineEmits(['show-detail', 'edit']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);

const socialServices = ref(props.data ? props.data.vulnerability_level == 1 : false);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $PersonApiService.getDetail(props.id);
    localData.value = detail;
    socialServices.value = detail.vulnerability_level == 1;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }


};

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
      }}</span>
  </div>

  <div v-else-if="localData">
    <div class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("common.person_id")' :value=localData.token></FieldDetail>
      <div class="flex items-center justify-end px-4">
        <button v-if="localData.piggy_bank" @click="showDetail('PersonPiggyBankRegion', localData.piggy_bank.id)"
          :disabled="isSubRegion"
          class="flex items-center text-slate-500 gap-2 rounded px-2 py-1 border border-slate-300 enabled:hover:bg-slate-100 enabled:hover:text-slate-600 disabled:cursor-default truncate">
          <Icon name="fa6-solid:piggy-bank" class="text-slate-400" />
          <span class="text-sm">
            {{ t('contract_block.balance') }}: {{ formatMoneyWithCurrency(localData.piggy_bank.amount) }}
          </span>
        </button>
      </div>
      <FieldDetail :label='$t("common.name")' :value=localData.full_name></FieldDetail>
      <FieldDetail v-if="localData.is_juridic && localData.current_record" :label='$t("billing_block.current_record")' 
        :value=localData.current_record></FieldDetail>
      <div class="col-span-2 flex items-center gap-2">
        <div class="flex items-center ml-1 text-slate-500">
          <input v-model="localData.is_juridic" type="checkbox" id="is_juridic" name="is_juridic" class="checkbox"
            :disabled="true" />
          <label for="is_juridic" class="ml-2"> {{ t('contract_block.is_juridic') }}</label>
        </div>
        
        <div v-if="!localData.is_juridic" class="flex items-center ml-2 text-slate-500">
          <input v-model="socialServices" type="checkbox" id="socialServices" name="socialServices" class="checkbox"
            :disabled="true" />
          <label for="socialServices" class="ml-2"> {{ t('contract_block.in_social_risk') }}</label>
        </div>

      </div>


    </div>

  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
