<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import RouteDetail from '~/components/molecules/RouteDetail.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import Draggable from 'vuedraggable';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  position_id: Number
});

const router = useRouter();
const { $RouteApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const showRegion = ref(false);

const emit = defineEmits(['change']);

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $RouteApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const emitChange = async (element) => {
  let new_position = { 'id': element.id, 'position_num': element.position }
  const result = await $RouteApiService.updateRoutePosition(new_position);
  getData();
  emit('change', result);

}

const positionClicked = (pos) => {
  const index = data.value.positions.findIndex(sp => sp.token == pos.token);
  if (index == -1) {
    data.value.positions.push(pos);
  }
  else {
    data.value.positions.splice(index, 1)
  }
  setTimeout(() => {
    closeAllRegions();
  }, 200)
};



const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

watch(() => props.id, () => {
  getData();
});

const edit = function () {
  navigateTo('/service/routes/edit/' + props.id);
}

getData();


</script>

<template>
  <div class="region__content">

    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else>
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('service_block.route_positions') }}</H1Region>
        <OptionsDropdown id="ConnectionRequestRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('route')}`" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>


      <div v-if="data" id="item_data" :data-rel=id>
        <RouteDetail :id="props.id" :data="data"></RouteDetail>

        <Draggable v-model="data.positions" itemKey="id" handle=".handle-move" class="dragArea" @end="onDraggableEnd"
          tag="div" :options="{ animation: 200 }">
          <template #item="{ element, index }">
            <div
              class="group grid grid-cols-[1fr,2fr,2fr] divide-x text-sm text-center leading-4 border-b transition-all duration-100"
              :class="{ 'bg-yellow-100': element.id == props.position_id }"
              style="margin-top: 0; margin-bottom: 0; padding-top: 0; padding-bottom: 0;">
              <!-- First Column -->
              <div class="text-slate-800 flex items-center px-2 py-0">
                <div class="handle-move cursor-move text-slate-900 border-r w-7 pr-1 flex items-center justify-center">
                  <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500 block-inline mr-1" />
                  <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500" />
                </div>
                <div class="pl-1 flex-grow flex items-center">
                  <input type="text" @change="emitChange(element)" v-model="element.position"
                    class="input border-none px-2 py-0 text-center" :class="{
                      'invalid': attemptedSave && (element.token === '' || element.position == null)
                    }" :disabled="element.id != props.position_id" />
                </div>
              </div>

              <!-- Second Column -->
              <div class="text-slate-800 relative flex items-center justify-between px-2 py-0">
                <span>{{ element.token }}</span>
              </div>

              <!-- Third Column -->
              <div class="text-slate-800 relative flex items-center justify-between px-2 py-0">
                <span>{{ element.properties[0] }}</span>
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1/2 transform -translate-y-1/2 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="positionClicked(element)">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
          </template>
        </Draggable>



      </div><!-- end if data -->
    </div><!-- end if pending -->
  </div>
</template>
