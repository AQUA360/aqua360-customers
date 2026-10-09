<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';


const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean,
  supply_points: [Object],
  selected: Number
});

const emit = defineEmits(['show-detail']);

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

/** Siempre abre la región del punt de suministro (id del supply point, no del meter) */
const openSupplyPoint = function (supply_point) {
  const id = supply_point?.id;
  if (id != null) {
    emit('show-detail', 'SupplyPointRegion', id);
  }
}

</script>

<template>
  <div>
    <div v-if="supply_points && supply_points.length != 0" v-for="supply_point in supply_points">
      <div class="p-2" :class="[selected == supply_point.id ? 'bg-yellow-50' : '']">
        <div role="row" class="grid grid-cols-2">
          
          <FieldDetail :label='$t("common.supply")'>
            <button v-if="!isSubRegion" type="button" @click.stop="openSupplyPoint(supply_point)"
              class="text-start text-sky-500 underline">{{ supply_point?.token }}</button>
            <span v-else>{{ supply_point?.token }}</span>
          </FieldDetail>
          <!-- <FieldDetail :label='$t("Estat Subminis.")' value="Contractat"></FieldDetail> -->
          <FieldDetail :label='$t("service_block.supply_status")'>
            <AtomsColorBadge :color="supply_point?.status_color" :value="supply_point?.status_name"></AtomsColorBadge>
          </FieldDetail>
        </div>
        <div role="row" class="grid grid-cols-2">
          <FieldDetail :label='$t("address_block.address")'>{{ supply_point?.address_complete }}</FieldDetail>
          <FieldDetail v-if="supply_point.address_supply" :label='$t("service_block.install_address")'
            :value="supply_point?.address_supply"></FieldDetail>
          <FieldDetail v-if="supply_point.meter && supply_point.meter_id != props.id" :strong="true" :label='$t("Comptador")'>
            <button v-if="!isSubRegion" type="button" @click.stop="showDetail('MeterRegion', supply_point.meter_id)"
              class="text-start text-sky-500 underline">{{ supply_point?.meter }}</button>
            <span v-else>{{ supply_point?.token }}</span>
          </FieldDetail>
          <span v-if="supply_point?.meter_id == props.id" class="text-slate-400 italic mb-1">
            {{ t('informative_block.info_supply_meter') }}
          </span>
        </div>
      </div>
      <hr class="my-2" />
    </div>

    <div v-else class="">
      <div class="footering text-slate-500 p-2">
        {{ t('common.no_records') }}
      </div>
    </div>
  </div>
</template>