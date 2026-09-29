export function executionSummary(children) {
  const tasks = Array.isArray(children) ? children : []
  const done = tasks.filter((task) => task.status === "done").length
  const doing = tasks.filter((task) => task.status === "doing").length
  const todo = tasks.length - done - doing
  const blocked = tasks.filter((task) => task.blocked).length
  return {
    total: tasks.length,
    done,
    doing,
    todo,
    blocked,
    label: `${done} / ${tasks.length} 已完成`,
    detail: [doing ? `${doing} 项进行中` : "", todo ? `${todo} 项未开始` : ""].filter(Boolean).join(" · "),
  }
}

export function sourceTaskTitle(activity, tasks) {
  if (activity?.task_id == null) return ""
  return tasks.find((task) => task.id === activity.task_id)?.title ?? "执行任务"
}

export function defaultFactSelection(suggestions) {
  return [...new Set((suggestions ?? []).map((suggestion) => suggestion.text))]
}

export function preserveEditableDraft(currentValue, serverValue, isDirty) {
  return isDirty ? currentValue : serverValue
}

export function isCurrentFactSuggestionRequest(expectedTaskId, currentTaskId, expectedEpoch, currentEpoch) {
  return expectedTaskId === currentTaskId && expectedEpoch === currentEpoch
}
