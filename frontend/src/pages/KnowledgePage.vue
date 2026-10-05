<script setup lang="ts">
import FileDropzone from "../components/FileDropzone.vue"
import type { KnowledgeDocument, KnowledgeSyncSummary } from "../types"

const KNOWLEDGE_UPLOAD_ACCEPT = ".md,.txt,.docx,.pdf"
const KNOWLEDGE_UPLOAD_MAX_SIZE = 10 * 1024 * 1024

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
    <FileDropzone
      class="knowledge-dropzone"
      :accept="KNOWLEDGE_UPLOAD_ACCEPT"
      :max-size="KNOWLEDGE_UPLOAD_MAX_SIZE"
      :uploading="uploading"
      label="将资料拖到这里，或点击选择文件"
      hint="Markdown / TXT / DOCX / PDF · 最大 10 MB"
      @file-selected="emit('upload', $event)"
    />
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
