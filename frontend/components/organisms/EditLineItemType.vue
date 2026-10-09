<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';

import AddBillingRange from '../molecules/AddBillingRange.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  pr_id: Number,
  inPriceRate: {
    type: Boolean,
    default: false
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  canChange: {
    type: Boolean,
    default: true
  }
});

const { $LineItemTypeApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const data = ref(null);

const selectedLineItemType = ref(null)

const showRegion = ref(false);

const emit = defineEmits(['show-subregion', 'show-detail']);

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const response = await $LineItemTypeApiService.getAll('', [], 1, null, false, props.id);
    data.value = []

    response.results.forEach(item => {
      data.value.push({
        value: item.id,
        label: item.name,
        billing_period: item.billing_period,
      })
    })
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}



const editLineItemType = function (element) {
  
  return navigateTo({
    path: '/pricing/line-item-types/edit/' + element,
    query: {
      pr_id: props.pr_id.id,
      br_id: props.id,
      inpr: props.inPriceRate
    }
  })
}

const createLineItemType = function () {
  return navigateTo({
    path: '/pricing/line-item-types/add',
    query: {
      pr_id: props.pr_id.id,
      br_id: props.id,
      inpr: props.inPriceRate
    }
  })
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
        <p>{{ $t('common.error') }}: {{ error.message }}</p>
        <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
            }}</button></p>
      </div>
      <div v-else>

        <div v-if="props.id" :class="{ 'mt-1': data.length == 0 }" class="text-gray-900 rounded shadow">

          <table class="min-w-full text-sm text-slate-800">
            <!-- <thead>
              <tr class="bg-gray-100 border-b text-left">
                <th class="p-2">{{t('Token')}}</th>
              </tr>
            </thead> -->
            <tbody>
              <tr v-for="(element, index) in data" :key="element.id" class="border-b bg-slate-50">
                <td v-if="!isSubRegion" class="p-2">
                  <button v-if="canChange" class="px-2 py-1 text-gray-500" @click="editLineItemType(element.value)"><Icon name="fa6-solid:pencil"/></button>
                  <a href="#" class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
                    @click="showDetail('LineItemTypeRegion', element.value)">{{ element.label }}</a>
                </td>
                <td v-else class="p-2">
                  <button :disabled="!canChange" class="cursor-pointer border text-sm w-8 h-8 right-3 top-3 rounded-md text-slate-600 mr-2" @click="editLineItemType(element.value)"><Icon name="fa6-solid:pencil"/></button>
                  {{ element.label }}
                </td>
                
              </tr>
            </tbody>
          </table>


          <div class="footering">
            <button v-if="canChange" @click="createLineItemType"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
            </button>

          </div>
        </div>



      </div><!-- end if data -->
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
