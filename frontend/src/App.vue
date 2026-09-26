<script setup lang="ts">
import { onMounted, ref } from "vue"

type ServiceStatus = "checking" | "ok" | "error"

const status = ref<ServiceStatus>("checking")

onMounted(async () => {
  try {
    const response = await fetch("/api/health")
    if (!response.ok) throw new Error("health check failed")

    const data = await response.json()
    status.value = data.status === "ok" ? "ok" : "error"
  } catch {
    status.value = "error"
  }
})

const statusText = {
  checking: "正在检查服务",
  ok: "前端、API 与数据库连接正常",
  error: "服务连接异常",
}
</script>

<template>
  <main class="shell">
    <section class="panel">
      <p class="eyebrow">TARS-GO PLATFORM</p>
      <h1>基础服务已就绪</h1>
      <p class="intro">高校机器人团队运营与协作平台。</p>

      <div class="status" :data-status="status">
        <span class="dot" aria-hidden="true"></span>
        {{ statusText[status] }}
      </div>
    </section>
  </main>
</template>
