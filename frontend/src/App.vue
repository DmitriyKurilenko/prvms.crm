<template>
  <RouterView />
  <PToast position="top-right" />
  <SoftPhone />
</template>

<script setup lang="ts">
import SoftPhone from '@/components/SoftPhone.vue'
</script>
