<script setup lang="ts">
function reloadPage() {
  window.location.reload()
}
</script>

<template>
  <section class="system-state" role="alert" aria-live="assertive">
    <span class="system-code">BASE / ERROR</span>
    <h1>页面加载失败</h1>
    <p>可能是版本刚刚更新，请重新加载页面。</p>
    <button class="secondary" type="button" @click="reloadPage">重新加载</button>
  </section>
</template>
