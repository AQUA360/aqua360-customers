<template>
  <div class="app-loading">
    <div class="drop-container">
      <!-- Background/Outline layer -->
      <img src="/loading.svg" class="drop-img grayscale-opacity" alt="loading-bg" />
      
      <!-- Filling layer -->
      <div class="fill-wrapper">
        <img src="/loading.svg" class="drop-img filled-drop" alt="loading-fill" />
      </div>
    </div>
    <p v-if="text" class="loading-text">{{ text }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  text: {
    type: String,
    default: ''
  },
  size: {
    type: Number,
    default: 80
  }
});

const sizeWithPx = computed(() => `${props.size}px`);
</script>

<style scoped>
.app-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.drop-container {
  position: relative;
  width: v-bind(sizeWithPx);
  height: v-bind(sizeWithPx);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drop-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.grayscale-opacity {
  filter: grayscale(100%);
  opacity: 0.2;
}

.fill-wrapper {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 0%;
  overflow: hidden;
  animation: water-fill 2.5s ease-in-out infinite;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.filled-drop {
  position: absolute;
  bottom: 0;
  left: 0;
  width: v-bind(sizeWithPx); /* Must match .drop-container width */
  height: v-bind(sizeWithPx); /* Must match .drop-container height */
  filter: drop-shadow(0 0 5px rgba(59, 130, 246, 0.5));
}

.loading-text {
  margin-top: 1.5rem;
  color: #64748b;
  font-weight: 500;
  letter-spacing: 0.025em;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes water-fill {
  0% {
    height: 0%;
  }
  70% {
    height: 100%;
  }
  100% {
    height: 100%;
    opacity: 0;
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
