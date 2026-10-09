<script setup>
import { ref, resolveDirective, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import LineItemTypeDetail from '../molecules/LineItemTypeDetail.vue';



const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  price_rate_id: Number,
  in_detail: {
    type: Boolean,
    default: false
  },
  canChange: true,
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['changed', 'show-detail']);
const { $LineItemTypeApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const getData = async () => {
  pending.value = true;

  try {
    if (props.id) {
      const response = await $LineItemTypeApiService.getAll('', [], 1, null, false, props.id);
      data.value = []

      response.results.forEach(item => {
        data.value.push(item)
      })
    }else{
      data.value = []
    }
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const editLineItemType = function (element) {
  
  return navigateTo({
    path: '/pricing/line-item-types/edit/' + element.id,
    query: {
      pr_id: props?.price_rate_id,
      br_id: element.billing_range.id,
      inprod: true
    }
  })
}

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

watch(() => props.id, () => {
  getData();
});


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
      <div v-if="data" id="item_data" :data-rel=id>
        <div v-for="element in data" :key="element.id" class="text-gray-900 rounded shadow">
          <details class="">
            <summary class="text-sm border-b p-2 text-slate-500 hover:bg-slate-200 active:bg-slate-300">
              <button v-if="canChange" class="px-2 py-1 text-gray-500 border rounded hover:bg-slate-300 hover:border-slate-500" 
              @click="editLineItemType(element)"><Icon name="fa6-solid:pencil"/></button>
              {{ element.name }}
            </summary>
            
            
            <LineItemTypeDetail :id="element.id" :data="element" :price_rate_id="props?.price_rate_id" :isSubRegion="isSubRegion" :isSubRegionOpen="true"
              class="pt-2 bg-sky-50 m-2 mb-2" @show-detail="showDetail" :in_detail="props.in_detail" :canChange="canChange">
                <!-- <template #button>
                  <button class="px-2 py-1 text-gray-500" @click="editLineItemType(element.value)"><Icon name="fa6-solid:pencil"/></button>
                </template> -->
              </LineItemTypeDetail>
          </details>
        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->
  </div><!-- end region__content -->
</template>
