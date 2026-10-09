<script setup>
// components/organisms/MeterRegion.vue
import { ref, watch, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import OptionsDropdown from '../molecules/OptionsDropdown.vue';
import DropdownOption from '../atoms/DropdownOption.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import ReadingDetail from '../molecules/ReadingDetail.vue';
import PiggyBankDetail from '../molecules/PiggyBankDetail.vue';
import BailRegion from './BailRegion.vue';
import PaymentRegion from './PaymentRegion.vue';
import ReturnPiggyBankRegion from '../molecules/ReturnPiggyBankRegion.vue';
import AddPiggyBankBalance from '../molecules/AddPiggyBankBalance.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import ManagePiggyBanksRegion from '../molecules/ManagePiggyBanksRegion.vue';
import { checkPermission } from '~/middleware/permission';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean,
  canChange: Boolean,
  isPerson: false
});

const emit = defineEmits(['show-subregion', 'changed']);

const router = useRouter();
const { $PiggyBankApiService, $PersonPiggyBankApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref(null);
const SubRegion = ref(props.isSubRegionOpen);
const persons = ref([]);
const objectPermissions = ref({ can_change: false, can_view: false });

const canChangePiggyBank = computed(() => {
  return props.canChange && objectPermissions.value.can_change;
});

const canViewPiggyBank = computed(() => {
  return objectPermissions.value.can_view;
});

const getData = async (load = true) => {
  pending.value = load;
  error.value = null;
  try {
    objectPermissions.value = await checkPermission(props.isPerson ? $PersonPiggyBankApiService : $PiggyBankApiService);
    if (!canViewPiggyBank.value) {
      error.value = { message: t('common.no_permissions') };
      return;
    }
    persons.value = [];
    if (!props.isPerson) {
      const result = await $PiggyBankApiService.getDetail(props.id);
      data.value = result;
      persons.value = [data.value.contract_holder];
      if (data.value.contract_tenant) {
        persons.value.push(data.value.contract_tenant);
      }
      if (data.value.contract_owner) {
        persons.value.push(data.value.contract_owner);
      }
    } else {
      const result = await $PersonPiggyBankApiService.getDetail(props.id);
      data.value = result;
      persons.value = [data.value.person];
    }

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const returnPiggyBank = async () => {
  try {
    await $PiggyBankApiService.returnMoney(props.id);
    await getData(false);
  } catch (err) {
    error.value = err;
  }
}

watch(() => props.id, () => {
  getData();
  regionDetailId.value = 0;
  closeSubRegion();
});


watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});


onMounted(() => {
  getData();
});


const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const onChangeRegion = () => {
  closeSubRegion();
  getData();
  emit('changed');
}


const closeSubRegion = function () {
  SubRegion.value = false;
  regionDetailId.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const edit = function () {
  navigateTo('/service/meters/edit/' + props.id);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p v-if="error.message !== t('common.no_permissions')"><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48%]': SubRegion }">
      <div class="relative flex justify-between">
        <H1Region class="mb-3">{{ $t('payment') }}</H1Region>
        <OptionsDropdown v-if="canChangePiggyBank" id="PiggyBankRegionOptions">
          <DropdownOption :name="`${t('billing_block.manage_piggy_banks')}`" @click="showDetail('ManagePiggyBanksRegion', props.id)"></DropdownOption>
        </OptionsDropdown>
      </div>


      <div v-if="data" id="item_data" :data-rel=id>

        <PiggyBankDetail :id="props.id" :isSubRegion="props.isSubRegion" :isSubRegionOpen="props.isSubRegionOpen"
          :data="data" @showDetail="showDetail" :isPerson="isPerson" :canChange="canChangePiggyBank"></PiggyBankDetail>

        <!-- <AtomsTabs>
          <li class="me-2">
            <a href="#tab_lectures" @click.prevent="setActiveTab('lectures')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'lectures', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'lectures' }">
              <Icon name="fa6-solid:list" class="display-inline mr-2" />{{ $t("Lectures") }}
            </a>
          </li>
        </AtomsTabs> -->
        <div id="tabpanels">

          <section v-show="activeTab === 'lectures'" role="tabpanel" id="tab_lectures"
            class="bg-white antialiased py-3">
            <ReadingDetail :meter_id="props.id" :isSubRegion="isSubRegion" @show-detail="showDetail" />
          </section>

        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->


    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden fixed top-0 right-0 z-30 w-[48%] overflow-y-auto"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <BailRegion v-if="showRegionDetailComponent === 'BailRegion'" :id="regionDetailId" :isSubRegion="true" />
        <PaymentRegion v-if="showRegionDetailComponent === 'PaymentRegion'" :id="regionDetailId" :isSubRegion="true" />
        <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId" :isSubRegion="true" />
        <ReturnPiggyBankRegion v-if="showRegionDetailComponent === 'ReturnPiggyBankRegion'" :id="regionDetailId" :isPerson="isPerson"
        :data="data" :persons="persons" @close="onChangeRegion" />
        <AddPiggyBankBalance v-if="showRegionDetailComponent === 'AddPiggyBankBalance'"
          :contractId="!isPerson ? data.contract_id : null"
          :personId="isPerson ? data.person?.id : null"
          :data="data"
          @change="onChangeRegion" @close="closeSubRegion" />
        <ManagePiggyBanksRegion v-if="showRegionDetailComponent === 'ManagePiggyBanksRegion'" :id="regionDetailId" 
        :isPerson="isPerson":data="data" @close="onChangeRegion" />
      </div>
    </div>

  </div><!-- end flex region-->
</template>