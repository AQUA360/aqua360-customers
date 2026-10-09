<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import H1Region from '~/components/atoms/H1Region.vue';

import AddBillingRange from '../molecules/AddBillingRange.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  inDetail: {
    type: Boolean,
    default: false
  },
  activeBillingRange: {
    type: Number,
    default: null
  },
  canChange: {
    type: Boolean,
    default: true
  }
});

const { $BillingRangeApiService} = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const data = ref(null);

const selectedBillingRange = ref(null)

const showRegion = ref(false);

const emit = defineEmits(['show-subregion', 'show-detail']);

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const response = await $BillingRangeApiService.getAll('',[],1,null,false,props.id);
    data.value = response.results
    

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}


const createBillingRange = () => {
  selectedBillingRange.value = null
  emit('show-subregion',{component: "AddBillingRange", id:selectedBillingRange.value})
}

const showDetail = function (component, id) {
  emit('show-subregion', { component: component, id: id })
}

watch(() => props.id, () => {
  getData();
});



getData();


</script>

<template>
  <div class="region__content">
    <div>

      <div v-if="pending">
        <p>{{ $t('common.loading') }}...</p>
      </div>
      <div v-else-if="error">
        <p>Error: {{ error.message }}</p>
        <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
            }}</button></p>
      </div>
      <div v-else-if="!inDetail">

        <div v-if="props.id" :class="{ 'mt-1': data.length == 0 }" class="text-gray-900 rounded shadow">

          <table class="min-w-full text-sm text-slate-800">
            <thead>
              <tr class="bg-gray-100 border-b text-left">
                <th class="p-2">{{t('common.identification')}}</th>
              <th class="p-2">{{t('pricing_block.publication_detail')}}</th>
              <th class="p-2">{{t('common.start')}}</th>
              <th class="p-2">{{t('common.end')}}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(element, index) in data" :key="element.id" class="border-b" :class="element.id != activeBillingRange ? 'bg-slate-50': 'bg-yellow-100 font-bold'">
                <td v-if="!isSubRegion" class="p-2">
                  <button class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
                  @click="showDetail('BillingRangeRegion', element.id)"
                  >{{ element.token }}</button>
                </td>
                <td v-else class="p-2">{{ element.token }}</td>
                <td v-if="!isSubRegion" class="p-2">
                  <button class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
                  @click="showDetail('PublicationRegion', element.publication.id)"
                  >{{ element.publication?.name }}</button></td>
                <td v-else class="p-2">{{ element.publication?.name }}</td>
                <td class="p-2">{{ formatDate(element.start) }}</td>
                <td class="p-2">{{ element.end ? formatDate(element.end) : '-' }}</td>
              </tr>
              <tr v-if="data.length == 0">
                <td colspan="4" class="p-2 text-center">{{ $t('common.no_data') }}</td>
              </tr>
            </tbody>
          </table>


          <div v-if="!isSubRegion && canChange" class="footering">
            <button @click="createBillingRange"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
            </button>
          </div>
        </div>



      </div><!-- end if data -->
      <div v-else>
        <p class="bg-yellow-100 p-2 mt-2 border">{{ $t('common.no_data') }}</p>
      </div>
    </div><!-- end if pending -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!--  -->
      </div>
    </div>
  </div>
</template>
