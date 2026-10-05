export function formatFileSize(bytes) {
  const megabytes = bytes / (1024 * 1024)
  if (megabytes >= 1) return `${Number.isInteger(megabytes) ? megabytes : megabytes.toFixed(1)} MB`
  const kilobytes = bytes / 1024
  return `${Number.isInteger(kilobytes) ? kilobytes : kilobytes.toFixed(1)} KB`
}

function mimeMatches(type, rule) {
  if (rule.endsWith("/*")) return type.startsWith(rule.slice(0, -1))
  return type === rule
}

export function matchesAcceptedFile(file, accept = "") {
  const rules = accept
    .split(",")
    .map((rule) => rule.trim().toLowerCase())
    .filter(Boolean)

  if (rules.length === 0) return true

  const extensionRules = rules.filter((rule) => rule.startsWith("."))
  const mimeRules = rules.filter((rule) => !rule.startsWith("."))
  const fileName = String(file.name || "").toLowerCase()
  const fileType = String(file.type || "").toLowerCase()

  if (extensionRules.length > 0 && !extensionRules.some((rule) => fileName.endsWith(rule))) {
    return false
  }

  if (fileType && mimeRules.length > 0 && !mimeRules.some((rule) => mimeMatches(fileType, rule))) {
    return false
  }

  if (extensionRules.length === 0 && mimeRules.length > 0 && !fileType) {
    return false
  }

  return true
}

export function validateFileSelection(file, { accept = "", maxSize = 0 } = {}) {
  if (!matchesAcceptedFile(file, accept)) return "不支持该文件格式。"
  if (maxSize > 0 && file.size > maxSize) return `文件不能超过 ${formatFileSize(maxSize)}。`
  return ""
}