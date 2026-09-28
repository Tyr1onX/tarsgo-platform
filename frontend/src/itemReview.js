const REVIEW_FIELDS = [
  ["title", "任务标题"],
  ["deliverable", "做到什么算完成"],
  ["execution_points", "执行提示"],
  ["cautions", "注意事项"],
  ["prerequisites", "开始前需要"],
]

function displayValue(value) {
  if (Array.isArray(value)) return value.length ? value.join("\n") : "（无）"
  return value || "（无）"
}

export function itemReviewChanges(current, proposed) {
  if (!current || !proposed) return []
  return REVIEW_FIELDS.flatMap(([field, label]) => {
    const before = current[field] ?? (field === "title" || field === "deliverable" ? "" : [])
    const after = proposed[field] ?? (field === "title" || field === "deliverable" ? "" : [])
    if (JSON.stringify(before) === JSON.stringify(after)) return []
    return [{ field, label, before: displayValue(before), after: displayValue(after) }]
  })
}

export function removeItemReviewSuggestion(suggestions, key) {
  return suggestions.filter((entry) => entry.key !== key)
}
