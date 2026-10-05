import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

import { validateFileSelection } from "../src/fileDropzone.js"

const page = await readFile(new URL("../src/pages/SchoolLeavePage.vue", import.meta.url), "utf8")
const dropzone = await readFile(new URL("../src/components/FileDropzone.vue", import.meta.url), "utf8")
const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const types = await readFile(new URL("../src/types.ts", import.meta.url), "utf8")
const style = await readFile(new URL("../src/style.css", import.meta.url), "utf8")

const schoolLeaveAccept = "image/jpeg,image/png,application/pdf,.jpg,.jpeg,.png,.pdf"
const schoolLeaveMaxSize = 15 * 1024 * 1024

// Existing member request workflow remains intact.
assert.match(page, /createSchoolLeaveRequest/)
assert.match(page, /updateSchoolLeaveRequest/)
assert.match(page, /withdrawSchoolLeaveRequest/)
assert.match(page, /type="time" step="300"/)
assert.match(page, /相同请假时间会自动汇总到同一份请假材料中/)

// Member state copy follows the completion loop.
assert.match(page, /item\.status === "pending"[^]*?"待汇总"/)
assert.match(page, /item\.run_status === "awaiting_return"[^]*?"办理中"/)
assert.match(page, /item\.run_status === "completed" && item\.result_state === "cleared"[^]*?"已完成 · 材料已清理"/)
assert.match(page, /item\.run_status === "completed"[^]*?"已完成"/)
assert.doesNotMatch(page, /已发送|标记已发送|markSent/)
assert.doesNotMatch(api, /markSchoolLeaveRunSent|\/sent/)

// Ready is a single download action; successful fetch is followed by a data refresh.
assert.match(page, /<h2>待下载 <span>· \{\{ readyRuns\.length \}\}<\/span><\/h2>/)
assert.match(page, />\s*下载请假材料\s*<\/button>/)
assert.match(page, /async function downloadRunDocument\(run: SchoolLeaveRun\)/)
const downloadBody = page.match(/async function downloadRunDocument\([^]*?\n}/)?.[0] ?? ""
assert.match(downloadBody, /api\.downloadSchoolLeaveRunDocument\(run\.id\)/)
assert.match(downloadBody, /await load\(\)/)
assert.match(api, /downloadSchoolLeaveRunDocument/)
assert.match(api, /\/api\/school-leave\/admin\/runs\/.*\/document/)

// Shared FileDropzone owns file selection UX, not School Leave business logic.
assert.match(page, /import FileDropzone from "\.\.\/components\/FileDropzone\.vue"/)
assert.doesNotMatch(page, /type="file"/)
assert.match(dropzone, /type="file"/)
assert.match(dropzone, /emit\("file-selected", file\)/)
assert.match(dropzone, /@click="openPicker"/)
assert.match(dropzone, /fileInput\.value\?\.click\(\)/)
assert.match(dropzone, /@keydown\.enter\.prevent="openPicker"/)
assert.match(dropzone, /@keydown\.space\.prevent="openPicker"/)
assert.match(dropzone, /@dragenter\.prevent="onDragEnter"/)
assert.match(dropzone, /@dragover\.prevent="onDragOver"/)
assert.match(dropzone, /@drop\.prevent="onDrop"/)
assert.match(dropzone, /dragDepth\.value \+= 1/)
assert.match(dropzone, /dragDepth\.value = Math\.max\(0, dragDepth\.value - 1\)/)
assert.match(dropzone, /"松开即可上传"/)
assert.match(dropzone, /将文件拖到这里，或点击选择文件/)
assert.match(dropzone, /const inactive = computed\(\(\) => props\.disabled \|\| props\.uploading\)/)
assert.match(dropzone, /if \(!file \|\| inactive\.value\) return/)
assert.match(dropzone, /:aria-disabled="inactive"/)
assert.match(dropzone, /:aria-busy="uploading \|\| undefined"/)

// Client validation accepts legal School Leave files, including empty MIME with a legal extension.
for (const file of [
  { name: "stamp.jpg", type: "image/jpeg", size: 1024 },
  { name: "stamp.jpeg", type: "", size: 1024 },
  { name: "stamp.png", type: "image/png", size: 1024 },
  { name: "stamp.pdf", type: "application/pdf", size: 1024 },
]) {
  assert.equal(validateFileSelection(file, { accept: schoolLeaveAccept, maxSize: schoolLeaveMaxSize }), "")
}
assert.equal(
  validateFileSelection(
    { name: "stamp.gif", type: "image/gif", size: 1024 },
    { accept: schoolLeaveAccept, maxSize: schoolLeaveMaxSize },
  ),
  "不支持该文件格式。",
)
assert.equal(
  validateFileSelection(
    { name: "stamp.pdf", type: "application/pdf", size: schoolLeaveMaxSize + 1 },
    { accept: schoolLeaveAccept, maxSize: schoolLeaveMaxSize },
  ),
  "文件不能超过 15 MB。",
)

// Awaiting-return UI is per exact group, with reusable dropzone, view and replacement controls.
assert.match(page, /awaitingReturnRuns = computed\(\(\) => runs\.value\.filter\(\(item\) => item\.status === "awaiting_return"\)\)/)
assert.match(page, /<h2>待老师回传 <span>· \{\{ awaitingReturnRuns\.length \}\}/)
const awaitingSection = page.slice(
  page.indexOf('<section v-if="awaitingReturnRuns.length"'),
  page.indexOf('<section v-if="pendingAdminRequests.length"'),
)
assert.match(awaitingSection, /v-for="group in run\.groups"/)
assert.match(awaitingSection, /<FileDropzone/)
assert.match(awaitingSection, /label="将文件拖到这里，或点击选择文件"/)
assert.match(awaitingSection, /hint="JPG \/ PNG \/ PDF · 最大 15 MB"/)
assert.match(awaitingSection, />\s*查看\s*<\/button>/)
assert.match(awaitingSection, />\s*重新上传\s*<\/button>/)
assert.match(page, /SCHOOL_LEAVE_RESULT_ACCEPT = "image\/jpeg,image\/png,application\/pdf,\.jpg,\.jpeg,\.png,\.pdf"/)
assert.match(page, /SCHOOL_LEAVE_RESULT_MAX_SIZE = 15 \* 1024 \* 1024/)
assert.match(api, /\/groups\/.*\/result/)
assert.match(api, /new FormData\(\)/)

// Upload state is isolated by run + group and never locks every group in a run.
assert.match(page, /function resultUploadKey\(runId: number, groupIndex: number\)/)
assert.match(page, /return `\$\{runId\}:\$\{groupIndex\}`/)
assert.match(page, /const uploadingResultKeys = ref<Record<string, boolean>>\(\{\}\)/)
assert.match(page, /:uploading="isResultUploading\(run\.id, group\.index\)"/)
const uploadBody = page.match(/async function uploadResult\([^]*?\n}/)?.[0] ?? ""
assert.match(uploadBody, /if \(uploadingResultKeys\.value\[key\]\) return/)
assert.match(uploadBody, /api\.uploadSchoolLeaveResult\(run\.id, groupIndex, file\)/)
assert.match(uploadBody, /resultUploadErrors\.value = \{ \.\.\.resultUploadErrors\.value, \[key\]: messageOf\(reason\) \}/)
assert.match(uploadBody, /uploadingResultKeys\.value = \{ \.\.\.uploadingResultKeys\.value, \[key\]: false \}/)
assert.doesNotMatch(uploadBody, /actionRunId\.value = run\.id/)
assert.match(page, /showReuploadDropzone\(run\.id, group\.index\)/)
assert.match(page, /reuploadDropzones\.value = \{ \.\.\.reuploadDropzones\.value, \[key\]: false \}/)

// Upload success collapses back to the existing uploaded state; failure leaves the same dropzone retryable.
assert.match(awaitingSection, /<span v-if="group\.result\?\.available">已上传<\/span>/)
assert.match(awaitingSection, /v-if="!group\.result\?\.available \|\| isReuploadDropzoneOpen\(run\.id, group\.index\)"/)
assert.match(page, /<p v-if="resultUploadError\(run\.id, group\.index\)" class="leave-upload-error">/)
assert.match(dropzone, /<strong v-if="uploading && selectedFileName">\{\{ selectedFileName \}\}<\/strong>/)
assert.match(dropzone, /<small v-if="uploading && selectedFileName">上传中…<\/small>/)

// Completion is fully derived from result data; no manual completion control exists.
assert.match(page, /completedRuns = computed\(\(\) => runs\.value\.filter\(\(item\) => item\.status === "completed"\)\)/)
assert.match(page, /<h2>已完成<\/h2>/)
assert.doesNotMatch(page, /标记完成|completeSchoolLeave|finishSchoolLeave/)

// Completed history keeps original Word re-download and uses the same FileDropzone for replacement.
const historySection = page.slice(page.indexOf('<section class="leave-history-section">'), page.indexOf("</template>\n</template>"))
assert.match(historySection, /downloadRunDocument\(run\)/)
assert.match(historySection, />\s*重新上传\s*<\/button>/)
assert.match(historySection, /<FileDropzone/)
assert.match(historySection, /openResult\(run\.id, group\.index\)/)
assert.match(historySection, /<ActionMenu/)
assert.match(page, /label: "删除记录"/)
assert.doesNotMatch(page, /class="leave-more"/)

// Member result access is shown only for completed + available result on that request.
assert.match(page, /item\.run_status === 'completed'/)
assert.match(page, /item\.result_state === 'available'/)
assert.match(page, /item\.run_id !== null/)
assert.match(page, /item\.group_index !== null/)
assert.match(page, />\s*下载盖章材料\s*<\/button>/)
assert.match(page, /api\.schoolLeaveResultUrl\(runId, groupIndex\)/)

// Lightweight admin todo count uses summary only, not all School Leave records in App.
assert.match(api, /schoolLeaveAdminSummary/)
assert.match(api, /\/api\/school-leave\/admin\/summary/)
assert.match(app, /const schoolLeaveTodoCount = ref\(0\)/)
assert.match(app, /api\.schoolLeaveAdminSummary\(\)/)
assert.match(app, /schoolLeaveTodoCount\.value = \(await api\.schoolLeaveAdminSummary\(\)\)\.todo_count/)
assert.match(app, /请假 <span v-if="isAdmin && schoolLeaveTodoCount" class="nav-count"/)
assert.match(app, /@todo-count="schoolLeaveTodoCount = \$event"/)
assert.match(style, /\.nav-count \{/)

// Types expose only the new state model and safe result metadata.
assert.match(types, /SchoolLeaveRunStatus = "ready" \| "awaiting_return" \| "completed" \| "cancelled"/)
assert.doesNotMatch(types, /SchoolLeaveRunStatus = [^\n]*"sent"/)
assert.match(types, /result_state: SchoolLeaveResultState \| null/)
assert.match(types, /group_index: number \| null/)
assert.match(types, /interface SchoolLeaveGroupResult/)
assert.match(types, /available: boolean/)
assert.doesNotMatch(types, /stored_path|stored_name/)

// Dropzone stays compact and responsive; mobile keeps system file selection without depending on drag/drop.
assert.match(dropzone, /width: 100%/)
assert.match(dropzone, /min-width: 0/)
assert.match(dropzone, /box-sizing: border-box/)
assert.match(dropzone, /min-height: 64px/)
assert.match(dropzone, /@media \(max-width: 520px\)/)
assert.match(dropzone, /点击选择文件/)
assert.doesNotMatch(dropzone, /min-height:\s*(?:[12]\d\d|[3-9]\d\d)px/)
assert.match(page, /@media \(max-width: 520px\)/)
assert.match(page, /\.leave-form-controls \{ grid-template-columns: minmax\(0, 1fr\); \}/)
assert.doesNotMatch(page, /width:\s*100vw/)
assert.doesNotMatch(page, /min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)
assert.doesNotMatch(page + app, /通知中心|通用待办|Todo Center|dashboard/i)

// School Leave remains independent from task/profile permission models.
assert.match(app, /path === '\/leave'/)
assert.match(app, /<SchoolLeavePage/)
assert.match(api, /schoolLeaveRequests/)
assert.match(api, /schoolLeaveRuns/)
assert.match(api, /deleteSchoolLeaveRun/)
assert.doesNotMatch(types, /interface MemberSummary \{[^}]*student_id/s)

console.log("School Leave drag-and-drop frontend tests passed")