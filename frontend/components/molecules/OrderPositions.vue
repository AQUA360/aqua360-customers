<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1 from '~/components/atoms/H1.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import _ from 'lodash';
import Draggable from 'vuedraggable';
import { id } from 'date-fns/locale';

const { t } = useI18n();
const { $RouteApiService, $AddressHelper } = useNuxtApp();

const emits = defineEmits([]);

const props = defineProps( {
  route_id: Number,
  route_name: String,
  selected_positions: Array,
  new_position_id: Number
});

const selected_positions = ref([])
const new_position_id = ref(null);

onMounted(() => {
  if (props.selected_positions) selected_positions.value = props.selected_positions;
  if (props.new_position_id) new_position_id.value = props.new_position_id;
});

const onDraggableEnd = () => {
  selected_positions.value.forEach((element, index) => {
    element.position = index + 1;
  });

  const selectedOptions = {
    id: props.route_id,
    position_ids: selected_positions.value.map(p => p.id)
  };
  $RouteApiService.updateRoute(selectedOptions);
}

watch(() => props.new_position_id, () => {
  new_position_id.value = props.new_position_id;
})
watch(() => props.selected_positions, () => {
  selected_positions.value = props.selected_positions;
})

</script>

<template>
  <div class="mb-2 row col-span-2 gap-3">
    <div class="field mb-3">
      <div class="flex">
        <H1>{{ props.route_name }}</H1>
      </div>
    </div>
    <div :class="{ 'mt-1': selected_positions.length == 0 }" class="text-gray-900 rounded shadow">
      <div v-if="selected_positions.length > 0"
        class="group grid grid-cols-[1fr,2fr,3fr,3fr] divide-x text-sm text-center border-b leading-4 ">
        <span class="p-1 text-slate-400"> {{ t('order') }} </span>
        <span class="p-1 text-slate-400"> {{ t('common.identification') }} </span>
        <span class="p-1 text-slate-400"> {{ t('property') }} </span>
        <span class="p-1 text-slate-400"> {{ t('address_block.address') }} </span>
      </div>

      <Draggable v-model="selected_positions" itemKey="id" handle=".handle-move" class="dragArea" @end="onDraggableEnd"
        tag="div" :options="{ animation: 200 }" >
        <template #item="{ element, index }">
          <div :class="{ 'bg-green-300': element.id == new_position_id, 'rounded-b': index == selected_positions.length - 1 }"
            class="group grid grid-cols-[1fr,2fr,3fr,3fr] divide-x text-sm text-center leading-4 border-b transition-all duration-100">
            <div class="p-2 text-slate-800 flex">
              <div class="handle-move cursor-move text-slate-900 border-r w-7 pr-1">
                <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500 block-inline mr-1" />  
                <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500" />
              </div>
              <div class="pl-1">
                {{ element.position }}
              </div>
            </div>
            <div class="p-2 text-slate-800">{{ element.token }}</div>
            <div class="p-2 text-slate-800 relative">
              <span v-for="property, i in element.properties">{{ i > 0 ? ', ' + property : property }} </span>
            </div>
            <div class="p-2 text-slate-800">
              {{ $AddressHelper.getAddressString(element) }}
            </div>
          </div>
        </template>
      </Draggable>
    </div>
  </div>
</template>

<style scoped>
.sortable-chosen {
  @apply bg-yellow-100
}
</style>