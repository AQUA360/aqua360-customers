<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import ClaimRequestDetail from '../molecules/ClaimRequestDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ClaimStepDetail from '../molecules/ClaimStepDetail.vue';
import EditClaimSteps from './EditClaimSteps.vue';
import AddClaimStep from '../molecules/AddClaimStep.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed']);
const router = useRouter();
const { $ClaimRequestApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const SubRegion = ref(props.isSubRegionOpen);

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const activeTab = ref('all_steps');


const getData = async () => {
  pending.value = true;
  error.value = null;

  try {
    const result = await $ClaimRequestApiService.getClaimRequestStepTemplateDetail(props.id);
    data.value = result;
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

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

getData();

const refresh = async () => {
  closeSubRegion();
  getData()
  emit('changed')
}


const updateSubRegion = function () {
  getData();
  closeSubRegion();
  emit('changed')
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

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
        <H1Region class="mb-3">
          {{ $t('billing_block.non_payment') }}

        </H1Region>
        <div class="relative">
          <OptionsDropdown v-if="!isSubRegion" id="ClaimStepRegionOptions">

          </OptionsDropdown>
        </div>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <ClaimStepDetail @show-detail="showDetail" @change="updateSubRegion()" :id="props.id" :data="data"
          :isSubRegion="isSubRegion" />

        <AtomsTabs>

          <li class="me-2">
            <a href="#tab_all_steps" @click.prevent="setActiveTab('all_steps')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'all_steps', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'all_steps' }"
              class="inline-flex items-center justify-center p-4 border-b-2 rounded-t-lg group" aria-current="page">
              <Icon name="fa6-solid:sitemap" class="display-inline mr-2" /> {{ $t("billing_block.steps") }}
            </a>
          </li>


        </AtomsTabs>

        <div id="claim_step_tabpanels">


          <section v-show="activeTab === 'all_steps'" role="tabpanel" id="tab_all_steps" class="bg-white antialiased">
            <div class="p-2">
              <EditClaimSteps :step="data" :isSubRegion="isSubRegion" @show-detail="showDetail" />
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
        <ClaimStepRegion v-if="showRegionDetailComponent === 'ClaimStepRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <AddClaimStep v-if="showRegionDetailComponent === 'ClaimStepEdit'" :id="regionDetailId"
          :isSubRegion="true" @change="refresh()" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
