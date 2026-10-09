<script setup>

const props = defineProps({
  isContractSubregion: Boolean,
  adjustments: Array,
  price_rate_id: {
    type: Number,
    default: null
  },
  isSubRegion: Boolean,
  in_detail: Boolean,
  hideActions: Boolean,
  canChange: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['show-detail', 'edit-adjustment', 'create-adjustment']);

function showDetail(type, id) {
  emit('show-detail', type, id);
}

function editAdjustment(id, new_tab) {
  emit('edit-adjustment', id, new_tab);
}

function createAdjustment() {
  emit('create-adjustment');
}
</script>

<template>
  <details class="mb-3">
    <summary class="text-sm p-2 text-slate-500 hover:bg-slate-200 active:bg-slate-300 cursor-pointer mb-2">
      <Icon name="fa6-solid:wrench" class="display-inline mr-2" />

      {{ !props.isContractSubregion ? $t('pricing_block.adjustments') : $t('pricing_block.contract_adjustments') }} ({{
        adjustments.length }})

    </summary>
    <div :class="{ 'mt-1': adjustments.length == 0 }" class="text-gray-900 mx-3 rounded">

      <table v-if="adjustments.length > 0" class="min-w-full text-sm text-slate-800">
        <thead>
          <tr class="bg-gray-100 border-b text-left">
            <th class="p-2">{{ $t('common.short_preference') }}</th>
            <th class="p-2">{{ $t('common.identificator') }}</th>
            <th class="p-2">{{ $t('common.operation') }}</th>
            <th class="p-2">{{ $t('pricing_block.short_var_cal') }}</th>
            <th class="p-2">{{ $t('common.quantity') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(element, index) in adjustments" :key="element.id" class="border-b"
            :class="element.end ? 'bg-slate-50' : 'bg-slate-50 font-bold'">
            <td class="p-2">{{ element.position }}</td>
            <td v-if="(!isSubRegion && !in_detail) || (isContractSubregion)" class="p-2">
              <a href="#" class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1 truncate"
                @click.prevent="showDetail('AdjustmentRegion', element.id)">{{ element.name }}</a>
            </td>
            <td v-else class="p-2">
              <div class="flex items-start gap-2">
                <button class="px-2 py-1 text-gray-500 hover:bg-slate-200 rounded active:bg-slate-300 flex-shrink-0"
                  @click="editAdjustment(element.id, true)">
                  <Icon name="fa6-solid:arrow-up-right-from-square" />
                </button>
                <button class="px-2 py-1 text-gray-500 hover:bg-slate-200 rounded active:bg-slate-300 flex-shrink-0"
                  @click="editAdjustment(element.id, false)">
                  <Icon name="fa6-solid:pencil" />
                </button>
                <!-- <NuxtLink :to="`/pricing/adjustments/add?adjustment_id=${element.id}&line_item_type_id=${element.line_item_type}&price_rate_id=${price_rate_id}`"  
                  class="px-2 py-1 text-gray-500 hover:bg-slate-200 rounded active:bg-slate-300 flex-shrink-0"
                  ><Icon name="fa6-solid:pencil" class="" /></NuxtLink> -->
                <div class="flex-1 min-w-0">
                  <span class="truncate block max-w-[90%]">
                    {{ element.name }}
                  </span>
                  <span v-if="element.conditions.length > 0" class="text-slate-500 text-sm"><span>{{ element.conditions.length
                      }}</span> {{ $t('pricing_block.conditions_to_apply') }}</span>
                  <span v-else class="text-slate-500 text-sm">-- {{ $t('pricing_block.always_apply') }}</span>
                </div>
              </div>
            </td>
            
            <td class="p-2">{{ element.operation.name }}</td>
            <td class="p-2">{{ element.variable_calculation.name }}</td>

            <td v-if="element.adjustment_interval_stretches && element.adjustment_interval_stretches.length > 0"
              class="p-2"><em>{{ $t('common.range') }}</em></td>
            <td v-else-if="element.variable_type" class="p-2">{{ element.variable_type.name }}</td>
            <td v-else-if="element.formula" class="p-2"><abbr :title="element.formula" class="cursor-help"><Icon name="fa6-solid:square-root-variable" /><Icon name="fa6-solid:question" /></abbr></td>
            <td v-else class="p-2">{{ element.quantity }}</td>

          </tr>
        </tbody>
      </table>
      <p v-else-if="adjustments.length == 0" class="text-slate-500 p-1">{{ $t('pricing_block.no_adjustments') }}</p>
      <div v-if="!hideActions && canChange" class="footering">
        <button @click="createAdjustment"
          class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300 bg-white">
          <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
        </button>
      </div>
    </div>
  </details>
</template>

<style scoped>
.footering {
  margin-top: 1rem;
}
</style>