<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';

const { $AddressHelper } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
});

const emit = defineEmits(['show-detail', 'clickChangeStatus']);

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

</script>

<template>
  <div id="wrapper" class="text-base">
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("product")' :value=data.name />
      <FieldDetail :label='$t("pricing_block.related_product")' v-if="data.product_related">
        <button @click="showDetail('ProductRegion', data.product_related)" class="text-start text-sky-500 underline">
          <span>{{ data.product_related_name }}</span>
        </button>
      </FieldDetail>
    </div>
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("common.origin")' :value=data.origin.name />

      <FieldDetail :label='$t("exploitation")'>
        <button v-if="!isSubRegion && data.exploitation" @click="showDetail('ExploitationRegion', data.exploitation.id)"
          class="text-start text-sky-500 underline">
          <span>{{ data.exploitation ? data.exploitation.name : '-' }}</span>
        </button>
        <span v-else>{{ data.exploitation ? data.exploitation.name : '-' }}</span>
      </FieldDetail>

      <FieldDetail :label='$t("company")'>
        <button v-if="!isSubRegion && data.company" @click="showDetail('CompanyRegion', data.company.id)"
          class="text-start text-sky-500 underline">
          <span>{{ data.company ? (data.company.alias || data.company.name) : '-' }}</span>
        </button>
        <span v-else>{{ data.company ? (data.company.alias || data.company.name) : '-' }}</span>
      </FieldDetail>

      <div class="flex items-center ml-2 text-slate-500">
        <input v-model="data.billing_active" type="checkbox" id="billing_active" name="billing_active" class="checkbox"
          :disabled="true" />
        <label for="billing_active" class="ml-2"> {{ t('pricing_block.billing_registration') }}</label>
      </div>
      <div class="flex items-center ml-2 text-slate-500">
        <input v-model="data.billing_inactive" type="checkbox" id="billing_inactive" name="billing_inactive" class="checkbox"
          :disabled="true" />
        <label for="billing_inactive" class="ml-2"> {{ t('pricing_block.billing_termination') }}</label>
      </div>
    </div>

  </div>

</template>
