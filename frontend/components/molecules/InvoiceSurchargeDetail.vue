<script setup>
import { formatDate } from '~/utils/date';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
const { t } = useI18n();

const props = defineProps({
  item: Object,
  isSubRegion: Boolean
});

const emit = defineEmits(['show-region']);

const { $InvoiceApiService } = useNuxtApp();

const childSurcharges = ref([])
const pending = ref(true)

const showDetail = function (component, id) {
  emit('show-region', component, id)
}

onMounted(() => {
})

</script>

<template>
  
  <div v-if="item.child_invoices?.length > 0" class="mb-10">
    <table class="min-w-full text-sm text-slate-800 mt-2">
      <thead>
        <tr class="bg-gray-100 border-b text-left">
          <th class="p-2">{{ t('common.identification') }}</th>
          <th class="p-2">{{ t('common.status') }}</th>
          <th class="p-2">{{ t('common.total') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(element, index) in item.child_invoices" :key="element.id" class="border-b">
          <td class="p-2">
            <button v-if="!isSubRegion" class="text-start text-sky-500 underline"
              @click="showDetail('InvoiceRegion', element.id)">
              {{ element.serie_final }}
            </button>
            <span v-else>{{ element.serie_final }}</span>
          </td>
          <td class="p-2">
            <AtomsColorBadge :value="element.status_name" :color="element.status_color"></AtomsColorBadge>
          </td>
          <td class="p-2">
            <span>{{ formatMoneyWithCurrency(element.total) }}</span>
          </td>
        </tr>

      </tbody>
    </table>
  </div>
  <div>
    <div v-if="item.parent_invoice && (item.parent_invoice.id != item.id)">

      <label class="block text-sm font-medium text-slate-700">{{ t('billing_block.parent_invoice') }}</label>
      
      <table class="min-w-full text-sm text-slate-800 mt-2">
        <thead>
          <tr class="bg-gray-100 border-b text-left">
            <th class="p-2">{{ t('common.identification') }}</th>
            <th class="p-2">{{ t('common.status') }}</th>
            <th class="p-2">{{ t('common.total') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-b">
            <td class="p-2">
              <button v-if="!isSubRegion" class="text-start text-sky-500 underline"
                @click="showDetail('InvoiceRegion', item.parent_invoice.id)">
                {{ item.parent_invoice.serie_final }}
              </button>
              <span v-else>{{ item.parent_invoice.serie_final }}</span>
            </td>
            <td class="p-2">
              <AtomsColorBadge :value="item.parent_invoice.status_name" :color="item.parent_invoice.status_color"></AtomsColorBadge>
            </td>
            <td class="p-2">
              <span>{{ formatMoneyWithCurrency(item.parent_invoice.total) }}</span>
            </td>
          </tr>

        </tbody>
      </table>
    </div>
  </div>

  <div v-if="!item.parent_invoice && item.child_invoices?.length === 0" class="text-slate-500">
    <p class="footering text-sm text-slate-500">
      {{ t('common.no_records') }}
    </p>
  </div>

</template>