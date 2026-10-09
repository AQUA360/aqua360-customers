<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

// Atomic UI
// - Assumim que AtomsFieldDetail existeix (mateix atom que uses al ContactDetail)
import AtomsFieldDetail from '~/components/atoms/AtomsFieldDetail.vue';

const { t } = useI18n();

const props = defineProps({
  /**
   * Pot ser:
   *  - person_address: { id, address_complete, address: { ... }, is_billing?, ... }
   *  - address: { id, postal_code, city, province, country, street, street_number, ... }
   */
  item: { type: Object, required: true },
  person: { type: Object, default: null },

  // Mostrar el nom de la persona com a títol/heading
  showPersonName: { type: Boolean, default: false },

  // Si true, la línia d’adreça es converteix en un link a mapes
  allowClick: { type: Boolean, default: true },

  // Mode compacte: només línia completa
  compact: { type: Boolean, default: true }
});

/**
 * Normalitza l'objecte address, vinguin d'un person_address o d'una address plana.
 */
const addressObj = computed(() => {
  // Si és person_address amb address embegut
  if (props.item?.address) {
    return props.item.address;
  }
  // Si ja és una address plana
  return props.item;
});

/**
 * Street label
 */
const streetTypeAbbr = computed(() => {
  // Variants suportades (segons AddAddress.vue i models que has mostrat)
  return (
    addressObj.value?.street?.type?.abbreviation ||
    addressObj.value?.street?.type_abbreviation ||
    addressObj.value?.street_type ||
    ''
  );
});

const streetName = computed(() => {
  return addressObj.value?.street?.name || addressObj.value?.street_name || '';
});

/**
 * Street number (amb rang i sufixos) — és flexible a diferents models.
 */
const numberType = computed(() => {
  // Preferim objecte estructurat
  return addressObj.value?.street_number?.number_type?.type ||
         addressObj.value?.street_number?.number_type_type ||
         addressObj.value?.street_number?.type ||
         'N';
});

const numberData = computed(() => {
  const sn = addressObj.value?.street_number;
  if (!sn) return null;

  const n  = sn.number ?? addressObj.value?.number ?? null;
  const ne = sn.number_end ?? addressObj.value?.number_end ?? null;
  const ns = sn.number_suffix ?? addressObj.value?.number_suffix ?? null;
  const nes = sn.number_end_suffix ?? addressObj.value?.number_end_suffix ?? null;

  return { n, ne, ns, nes };
});

const streetNumberText = computed(() => {
  // Sense número
  if (numberType.value === 'SN') return t('address_block.no_number');

  if (!numberData.value) return '';
  const parts = [];

  // Base
  if (numberData.value.n) {
    parts.push(`${numberData.value.n}${numberData.value.ns ? numberData.value.ns : ''}`);
  }

  // Rang
  if (numberType.value === 'R' && numberData.value.ne) {
    const endStr = `${numberData.value.ne}${numberData.value.nes ? numberData.value.nes : ''}`;
    if (parts.length > 0) {
      parts.push(`- ${endStr}`);
    } else {
      parts.push(endStr);
    }
  }

  return parts.join(' ');
});

/**
 * Línia de via principal: "TV NomVIA, Num"
 */
const lineVia = computed(() => {
  const type = streetTypeAbbr.value ? `${streetTypeAbbr.value} ` : '';
  const name = streetName.value || '';
  const num = streetNumberText.value ? `, ${streetNumberText.value}` : '';
  const via = `${type}${name}${num}`.trim();

  return via || null;
});

/**
 * Línia municipal: "CP Municipi, Província (País)"
 */
const postal = computed(() => addressObj.value?.postal_code || '');
const city = computed(() =>
  addressObj.value?.city?.name || addressObj.value?.city_name || addressObj.value?.city || ''
);
const province = computed(() =>
  addressObj.value?.province?.name || addressObj.value?.province_name || addressObj.value?.province || ''
);
const country = computed(() =>
  addressObj.value?.country?.name || addressObj.value?.country_name || addressObj.value?.country || ''
);

const lineMunicipal = computed(() => {
  const p = postal.value ? `${postal.value} ` : '';
  const c = city.value || '';
  const pr = province.value ? `, ${province.value}` : '';
  const co = country.value ? ` (${country.value})` : '';
  const s = `${p}${c}${pr}${co}`.trim();

  return s || null;
});

/**
 * Detalls de finca/portal
 */
const floor = computed(() => addressObj.value?.floor || '');
const door = computed(() => addressObj.value?.door || '');
const stair = computed(() => addressObj.value?.stair || '');
const building = computed(() => addressObj.value?.building || '');

const lineExtra = computed(() => {
  const parts = [];
  if (building.value) parts.push(`${t('address_block.building')}: ${building.value}`);
  if (stair.value) parts.push(`${t('address_block.stair')}: ${stair.value}`);
  if (floor.value) parts.push(`${t('address_block.floor')}: ${floor.value}`);
  if (door.value) parts.push(`${t('address_block.door')}: ${door.value}`);
  return parts.join(' · ');
});

/**
 * Si l’API ja ens dona un camp resumit
 */
const addressComplete = computed(() => {
  // Per person_address
  const fromPA = props.item?.address_complete;
  if (fromPA) return fromPA;

  // Alternativa: construir-la manualment
  // 1) línia de via
  // 2) línia municipal
  const via = lineVia.value || '';
  const mun = lineMunicipal.value || '';
  const extra = lineExtra.value || '';

  return [via, mun, extra].filter(Boolean).join(' — ');
});

</script>

<template>
  <div class="flex flex-col">
    <!-- Nom persona (opcional) -->
    <p v-if="person && showPersonName" class="mb-2 font-semibold">
      {{ person.full_name }}
    </p>

    <template v-else>
      <AtomsFieldDetail :label="$t('common.address')" :icon="'fa6-solid:location-dot'">
        <template #default>
          <div class="flex flex-col">
            <span v-if="lineVia" class="text-slate-800">
                {{ lineVia }}
            </span>
            <span v-if="lineMunicipal" class="text-slate-600 text-sm">{{ lineMunicipal }}</span>
            <span v-if="lineExtra" class="text-slate-500 text-xs mt-1">{{ lineExtra }}</span>
          </div>
        </template>
      </AtomsFieldDetail>
    </template>

    <!-- Bandera/indicador si és de facturació (si ve de person_address) -->
    <div v-if="item?.is_billing" class="text-xs text-emerald-700 mt-1">
      {{ $t('common.fiscal_address') }}
    </div>
  </div>
</template>