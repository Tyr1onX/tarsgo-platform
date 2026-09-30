<script setup lang="ts">
import { ref } from "vue"
import type { KnowledgeDocument, KnowledgeSyncSummary } from "../types"

defineProps<{
  documents: KnowledgeDocument[]
  uploading: boolean
  syncing: boolean
  summary: KnowledgeSyncSummary | null
  formatDate: (value: string) => string
  statusLabel: (document: KnowledgeDocument) => string
}>()

const emit = defineEmits<{
  upload: [file: File]
  sync: []
  remove: [document: KnowledgeDocument]
  navigate: [path: string]
}>()

const fileInput = ref<HTMLInputElement | null>(null)

function uploadSelectedFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit("upload", file)
  input.value = ""
}
</script>

<template>
  <div class="page-title">
    <div>
      <h1>团队资料</h1>
      <p>维护 AI 规划会使用的长期资料。</p>
    </div>
    <button type="button" @click="emit('navigate', '/team')">返回团队</button>
  </div>
  <section class="knowledge-actions">
    <button class="primary" type="button" :disabled="uploading" @click="fileInput?.click()">
      {{ uploading ? "正在上传…" : "上传资料" }}
    </button>
    <input ref="fileInput" class="visually-hidden" type="file" accept=".md,.txt,.docx,.pdf" :disabled="uploading" @change="uploadSelectedFile" />
    <small>支持 Markdown、TXT、DOCX 和可提取文字的 PDF，单个文件最大 10 MB。</small>
  </section>
  <details class="knowledge-maintenance">
    <summary>高级维护</summary>
    <button type="button" :disabled="syncing" @click="emit('sync')">
      {{ syncing ? "正在同步…" : "同步 GitHub 资料" }}
    </button>
  </details>
  <p v-if="summary" class="message success" role="status">
    同步完成：新增 {{ summary.added }}，更新 {{ summary.updated }}，未变化 {{ summary.unchanged }}，失败 {{ summary.failed }}，已移除 {{ summary.removed }}。
  </p>
  <section>
    <div class="section-heading"><h2>来源文件</h2><span>{{ documents.length }} 条</span></div>
    <div v-if="documents.length" class="knowledge-list">
      <article v-for="document in documents" :key="document.id" class="knowledge-row">
        <div>
          <span class="state">{{ document.source_type === 'github' ? 'GitHub' : '上传' }} · {{ statusLabel(document) }}</span>
          <h3>{{ document.display_name }}</h3>
          <small>{{ document.source_type === 'github' ? document.source_name : document.title }}</small>
          <small>更新于 {{ formatDate(document.synced_at) }}</small>
        </div>
        <button class="danger-text" type="button" @click="emit('remove', document)">删除</button>
      </article>
    </div>
    <div v-else class="empty empty-state">
      <span class="empty-code">KNOWLEDGE / EMPTY</span>
      <h3>还没有团队资料</h3>
      <p>可以从 GitHub 同步，或上传一份文档作为知识来源。</p>
    </div>
  </section>
</template>
