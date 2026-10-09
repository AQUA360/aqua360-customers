<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';

// Importar el component SupplyPointRegion per a la subregion
const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  province: Object,
  city: Object,
  streetName: String,
  selectedItem: Array,
  isSubRegion: false,
  isSubRegionOpen: Boolean,
  cadastreData: Array
});

const emit = defineEmits(['show-subregion', 'change', 'item-clicked']);
const { $CatastroApiService } = useNuxtApp();
const pending = ref(!props.cadastreData);
const error = ref(null);
const data = ref([]);
const callejero = ref(props.cadastreData || [])
const province = ref('');
const municipality = ref('');
const street_type = ref('');
const street_name = ref('');
const SubRegion = ref(props.isSubRegionOpen);


const itemClicked = ((item) => {
  props.selectedItem.push({
    id: item.id,
    cp: item.loine.cp,
    cm: item.loine.cm,
    cv: item.dir.cv,
    tv: item.dir.tv,
    nv: item.dir.nv
  })

  emit('item-clicked', item);

})

const getData = async (load_props = true) => {
  pending.value = true;
  error.value = null;
  try {
    if(load_props && props.city != null) {
      if(props.province){
        province.value = typeof props.province === 'object' ? props.province.label : props.province;
      } else {
        province.value = typeof props.city.province === 'object' ? props.city.province.name : props.city.province;
      }
      municipality.value = typeof props.city === 'object' ? props.city.label : props.city;

      if(props.streetName){
        street_name.value = typeof props.streetName === 'string' ? props.streetName : '';
      }
    }
    const result = await $CatastroApiService.getData(province.value, municipality.value, street_type.value, street_name.value);
    callejero.value = [];
    data.value = [];
    callejero.value = result.consulta_callejeroResult.callejero;

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

watch(() => [props.streetName, props.province, props.city], () => {
  getData(true);
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

watch(() => props.cadastreData, (newVal) => {
  if (newVal && newVal.length > 0) {
    callejero.value = newVal;
    pending.value = false;
  }
});

if (!props.cadastreData || props.cadastreData.length === 0) {
  getData();
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const showRegionDetailComponent = ref(null);

const emitChange = () => {
  emit('change', {
    street_type: street_type.value,
    street_name: street_name.value,
    province: province.value,
    municipality: municipality.value
  });
};

onMounted(() => {
  getData(true)
});


</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('common.cadastral') }}</H1Region>

      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <div class="heading grid grid-cols-[1fr,1fr] gap-3 text-base mb-1 items-center">
          <input type="text" id="province" v-model="province" :placeholder="t('address_block.province')" @change="emitChange"
            class="p-1 text-slate-400 border border-gray-300 rounded">
          </input>
          <input class="p-1 text-slate-400 border border-gray-300 rounded" id="municipality" v-model="municipality"
            @change="emitChange" :placeholder="t('address_block.municipality')">
          </input>

        </div>
        <div class="heading grid grid-cols-[1fr,1fr] gap-3 text-base mb-1 items-center">

          <input class="p-1 text-slate-400 border border-gray-300 rounded" id="street_type" v-model="street_type"
            :placeholder="t('common.type')" @change="emitChange" />
          <input class="p-1 text-slate-400 border border-gray-300 rounded" id="street_name" v-model="street_name"
            :placeholder="t('common.name')" @change="emitChange" />
          </div>

          <button @click="getData(false)" class="button-default-xs">
            <Icon name="fa6-solid:magnifying-glass" class="text-blue-500" />
            {{ $t('dashboard.search') }}
          </button>
        <div>
          <section class="bg-white antialiased py-3">
            <div v-if="pending">
              <p>{{ $t('common.loading') }}...</p>
            </div>

            <div v-else>
              <div v-for="items in callejero" :key="items.id">
                <div v-for="item in items" :key="item.id" @click="itemClicked(item)"
                  class="grid grid-cols-[250px,1fr] border bg-gray-100 hover:bg-yellow-100 border-gray-200 w-full p-1 block text-left mb-1">
                  <div class="p-2 text-slate-700 font-bold">
                    <span >{{ item.dir.tv }}-{{ item.dir.nv }}</span>
                  </div>
                  <div class="p-2 text-slate-800">
                    <span>Loine-Dir:  {{ item.loine.cp }}{{ item.loine.cm }}</span>
                    <span> - {{ item.dir.cv }} </span>
                  </div>

                </div>

              </div>
            </div>
          </section>
        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
      </div>
    </div>
  </div><!-- end region__content -->
</template>
