<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  request: Object,
  data: {
    type: Object,
    default: null,
  },
});
const emit = defineEmits(['clickChangeStatus', 'show-map']);

const { $SupplyCutApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $SupplyCutApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

onMounted(() => {
  if (props.data || props.request) {
    data.value = props.data || props.request;
    pending.value = false;
  } else if (props.id) {
    getData();
  }
});

watch(() => props.data, (newValue) => {
  if (newValue) {
    data.value = newValue;
    pending.value = false;
    error.value = null;
  }
}, { deep: true });

watch(() => props.id, () => {
  if (props.id && !props.data) {
    getData();
  }
});
</script>

<template>
  <div v-if="pending">
    <div class="border border-gray-300 rounded-b p-4 bg-white">
      <div class="flex justify-center items-center">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        <span class="ml-2">{{ $t('common.loading') }}...</span>
      </div>
    </div>
  </div>

  <div v-else-if="error">
    <p>Error: {{ error.message }}</p>
    <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button></p>
  </div>
  <div v-else>
    <div v-if="data" id="item_data" :data-rel=id>
      <div role="row" class="grid grid-cols-2">
        <FieldDetail :label="$t('common.code')" :value=data.token></FieldDetail>
      </div>
      <div role="row" class="grid grid-cols-2">
        <FieldDetail :label="$t('common.status')" class="pr-1">
          <AtomsColorBadge :value="data.status?.name" :color="data.status?.color"></AtomsColorBadge>
        </FieldDetail>
        <FieldDetail v-if="data.cause" :label="$t('order_block.reason')"  class="pr-1">
          <AtomsColorBadge :value="data.cause?.name" :color="data.cause?.color"></AtomsColorBadge>
        </FieldDetail>
      </div>
      <div role="row" class="grid grid-cols-2">
        <FieldDetail :label="$t('service_block.cut_date_expected_start')" :value="data.date_start ? formatDateTime(data.date_start) : '-'"></FieldDetail>
        <FieldDetail :label="$t('service_block.cut_date_expected_end')" :value=formatDateTime(data.date_end)>
          {{ data.date_end ? formatDateTime(data.date_end) : "-" }}
        </FieldDetail>
      </div>
      <div role="row" class="grid grid-cols-2">
        <FieldDetail :label="$t('service_block.cut_date_real_start')" :value="data.exec_start ? formatDateTime(data.exec_start) : '-'" />
        <FieldDetail :label="$t('service_block.cut_date_real_end')" :value="formatDateTime(data.exec_end)">
          {{ data.exec_end ? formatDateTime(data.exec_end) : "-" }}
        </FieldDetail>
      </div>

      <hr class="my-4 border-t border-gray-300" />

      <!--
        There used to be two fieldsets here (supply point data and "Generate
        work order", with an empty `generateWorkOrder()`) guarded by
        `v-if="data.supply_point"`. SupplyCut has no `supply_point` field (only
        the M2M `supply_points`), so they were never shown. All of that info
        and the real actions (work order, status change) are served by
        `SupplyCutRegion.vue` for the selected supply point, with permission
        checks.
      -->
    </div><!-- end if data -->
  </div><!-- end if pending -->
</template>
