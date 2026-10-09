<script setup>
const clipId = ref('drop-fill-clip-' + Math.random().toString(36).slice(2));
</script>

<template>
  <svg class="w-10 h-10 text-sky-500" viewBox="-3 -3 54 70" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <defs>
      <clipPath :id="clipId">
        <rect x="0" width="48" height="64">
          <animate attributeName="height" values="0;64;0" dur="1.8s" repeatCount="indefinite" />
          <animate attributeName="y" values="64;0;64" dur="1.8s" repeatCount="indefinite" />
        </rect>
      </clipPath>
    </defs>
    <!-- Drop outline (teardrop upside down: point at top, round at bottom) -->
    <path d="M24 0 C24 0 0 18 0 40 C0 58 12 64 24 64 C36 64 48 58 48 40 C48 18 24 0 24 0 Z" stroke="currentColor" stroke-width="3" fill="none" />
    <!-- Filling water (scaled inward so it sits inside the border) -->
    <g transform="translate(24 32) scale(0.82) translate(-24 -32)">
      <path d="M24 0 C24 0 0 18 0 40 C0 58 12 64 24 64 C36 64 48 58 48 40 C48 18 24 0 24 0 Z" fill="currentColor" :clip-path="'url(#' + clipId + ')'" />
    </g>
  </svg>
</template>
