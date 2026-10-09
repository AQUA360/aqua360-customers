<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

definePageMeta({
  layout: 'got'
});

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const toast = useToast();
const { $gotApi } = useNuxtApp();

const order = ref(null);
const reports = ref([]);
const loading = ref(true);
const observation = ref('');
const showFinalizeDialog = ref(false);
const finalizing = ref(false);
const addingObservation = ref(false);

// Operator assignment state
const showAssignModal = ref(false);
const assigningToMe = ref(false);
const currentOperatorId = ref(null);

const fetchOrder = async () => {
  loading.value = true;
  try {
    const response = await $gotApi.getOrderDetail(route.params.id);
    if (response.success) {
      order.value = response.order;
    } else {
      toast.error(t('common.error_load'));
    }
  } catch (error) {
    console.error('Error loading order:', error);
    toast.error(t('common.error_load'));
  } finally {
    loading.value = false;
  }
};

const fetchReports = async () => {
  try {
    const response = await $gotApi.getReports(route.params.id);
    if (response.success) {
      reports.value = response.reports || [];
    }
  } catch (error) {
    console.error('Error loading reports:', error);
  }
};

// Load current user's operator ID
const loadCurrentOperatorId = async () => {
  try {
    const response = await $gotApi.getLectureUsers();
    if (response.success) {
      const currentUser = response.lecture_users.find(u => u.is_current_user);
      if (currentUser) {
        currentOperatorId.value = currentUser.operator_id;
      }
    }
  } catch (error) {
    console.error('Error loading current operator:', error);
  }
};

const handleAddObservation = async () => {
  if (!observation.value.trim()) {
    toast.error(t('common.required_fields'));
    return;
  }

  addingObservation.value = true;
  try {
    const response = await $gotApi.addObservation(route.params.id, observation.value);
    if (response.success) {
      toast.success(t('GOT.observation_added'));
      observation.value = '';
      await fetchOrder(); // Reload to get updated observations
    } else {
      toast.error(t('common.error_save'));
    }
  } catch (error) {
    console.error('Error adding observation:', error);
    toast.error(t('common.error_save'));
  } finally {
    addingObservation.value = false;
  }
};

const handleFinalize = async () => {
  // Check if at least one report exists
  if (!reports.value || reports.value.length === 0) {
    toast.error(t('GOT.report_required_before_finalize'));
    return;
  }

  finalizing.value = true;
  try {
    const response = await $gotApi.finalizeOrder(route.params.id, {});
    if (response.success) {
      toast.success(t('GOT.finalize_success'));
      await navigateTo('/got/orders');
    } else {
      toast.error(t('common.error_save'));
    }
  } catch (error) {
    console.error('Error finalizing order:', error);
    toast.error(t('common.error_save'));
  } finally {
    finalizing.value = false;
    showFinalizeDialog.value = false;
  }
};

// Handle quick assign to me
const handleAssignToMe = async () => {
  assigningToMe.value = true;
  try {
    const response = await $gotApi.assignLectureUser(route.params.id, 'assign');
    if (response.success) {
      toast.success(t('GOT.assigned_to_me_success'));
      await fetchOrder(); // Reload to get updated operators
    } else {
      toast.error(t('GOT.assign_error'));
    }
  } catch (error) {
    console.error('Error assigning to me:', error);
    toast.error(t('GOT.assign_error'));
  } finally {
    assigningToMe.value = false;
  }
};

// Handle operators updated from modal
const handleOperatorsUpdated = async (assignedOperators) => {
  await fetchOrder(); // Reload to get updated operators
};

const handleBack = () => {
  const fromPage = route.query.from;
  if (fromPage === 'summary') {
    router.push('/got/summary');
  } else {
    router.push('/got/orders');
  }
};

const handleAddReport = () => {
  // Check if current user is assigned to this order
  if (!isCurrentUserAssigned.value) {
    toast.error(t('GOT.order_not_assigned_to_you'));
    return;
  }
  
  router.push(`/got/orders/create-report/${route.params.id}`);
};

// Check if order is editable (not completed)
const isEditable = computed(() => {
  return order.value && !order.value.completed_at;
});

// Check if current user is assigned to this order
const isCurrentUserAssigned = computed(() => {
  if (!order.value?.operators || !currentOperatorId.value) return false;
  return order.value.operators.some(op => op.id === currentOperatorId.value);
});

onMounted(() => {
  fetchOrder();
  fetchReports();
  loadCurrentOperatorId();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Back Button & Header -->
    <GotOrderHeader :order="order" @back="handleBack" />

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <Icon name="fa6-solid:spinner" class="animate-spin text-3xl text-gray-300" />
    </div>

    <!-- Content -->
    <div v-else-if="order" class="space-y-4">
      <!-- Order Info Card -->
      <div class="bg-white rounded-lg border border-gray-200/60">
        <div class="px-4 py-3 border-b border-gray-200/60 bg-gray-50/50 rounded-t-lg">
          <h2 class="text-base font-semibold text-gray-900">{{ order.type?.name || '-' }}</h2>
          <p v-if="order.reason" class="text-xs font-medium text-gray-500 italic">{{ order.reason?.name || '-' }}</p>
        </div>
        
        <!-- Description Section (sticky within card) -->
        <GotOrderDescription 
          :description="order.description" 
        />
        
        <div class="px-4 py-4">
          <div class="space-y-4"> 
            <!-- Supply Point Information -->
            <template v-if="order.supply_point">
              <GotOrderSupplyPoint :supply-point="order.supply_point" />
              <hr class="border-gray-200/60" />
            </template>

            <!-- Connection Information -->
            <template v-if="order.connection">
              <GotOrderConnection :connection="order.connection" />
              <hr class="border-gray-200/60" />
            </template>

            <!-- Address Information -->
            <template v-if="order.address">
              <GotOrderAddress :address="order.address" />
              <hr class="border-gray-200/60" />
            </template>

            <!-- Location (coordinates) -->
            <template v-if="order.latitude && order.longitude">
              <GotOrderLocation :latitude="order.latitude" :longitude="order.longitude" />
              <hr class="border-gray-200/60" />
            </template>

            <!-- Completed At -->
            <template v-if="order.completed_at">
              <GotOrderCompletedAt :completed-at="order.completed_at" />
              <hr class="border-gray-200/60" />
            </template>

            <!-- Operators (Editable) -->
            <GotOrderOperators 
              :operators="order.operators"
              :editable="isEditable"
              :current-operator-id="currentOperatorId"
              :assigning-to-me="assigningToMe"
              @edit="showAssignModal = true"
              @assign-to-me="handleAssignToMe"
            />
          </div>
        </div>
      </div>

      <!-- Reports History Section -->
      <div v-if="reports.length > 0" class="bg-white rounded-lg border border-gray-200/60 overflow-hidden">
        <GotReportsList :reports="reports" />
      </div>

      <!-- Observations Section (only if not completed) -->
      <div v-if="!order.completed_at" class="bg-white rounded-lg border border-gray-200/60 overflow-hidden">
        <!-- Observations History -->
        <GotObservationsList 
          v-if="order.observations && order.observations.length > 0"
          :observations="order.observations"
        />

        <!-- Add New Observation -->
        <GotAddObservationForm
          v-model="observation"
          :loading="addingObservation"
          :has-border="order.observations && order.observations.length > 0"
          @submit="handleAddObservation"
        />
      </div>
      
      <!-- Completed Message -->
      <GotOrderCompletedMessage
        v-else-if="order.completed_at"
        :observations="order.observations"
      />
    </div>

    <!-- Floating Finalize Button (only if not completed) -->
    <GotFinalizeOrderButton
      :show="order && !order.completed_at"
      @click="showFinalizeDialog = true"
    />

    <!-- Floating Add Report Button (only if not completed) -->
    <GotAddReportButton
      :show="order && !order.completed_at"
      @click="handleAddReport"
    />

    <!-- Finalize Dialog -->
    <GotFinalizeOrderDialog
      :show="showFinalizeDialog"
      :loading="finalizing"
      @close="showFinalizeDialog = false"
      @confirm="handleFinalize"
    />

    <!-- Assign Operators Modal -->
    <GotAssignOperatorsModal
      :show="showAssignModal"
      :order-id="route.params.id"
      :current-operators="order?.operators || []"
      @close="showAssignModal = false"
      @updated="handleOperatorsUpdated"
    />
  </div>
</template>
