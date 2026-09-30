export function taskMatchesView(task, view, memberId) {
  if (view === "all") return true
  if (view === "claimable") {
    return task.owner === null && task.owner_claimable && task.status !== "done"
  }
  return task.owner?.id === memberId || task.collaborators.some((member) => member.id === memberId)
}

export function claimableTask(task) {
  return task.owner === null && task.owner_claimable && task.status !== "done"
}

export function deriveRootStatus(children) {
  if (!children.length || children.every((task) => task.status === "todo")) return "todo"
  if (children.every((task) => task.status === "done")) return "done"
  return "doing"
}

export function patchTaskCollection(current, updated, view, memberId, hasCompleteChildren = false) {
  const next = current.filter((task) => task.id !== updated.id)
  if (taskMatchesView(updated, view, memberId)) next.push(updated)

  if (hasCompleteChildren && updated.parent_id !== null) {
    const rootIndex = next.findIndex((task) => task.id === updated.parent_id)
    const children = next.filter((task) => task.parent_id === updated.parent_id)
    if (rootIndex >= 0 && children.length) {
      next[rootIndex] = { ...next[rootIndex], status: deriveRootStatus(children) }
    }
  }

  return next.sort((left, right) =>
    new Date(left.deadline).getTime() - new Date(right.deadline).getTime() || left.id - right.id,
  )
}

export function setPendingTaskAction(current, taskId, action) {
  const next = new Map(current)
  if (action === null) next.delete(taskId)
  else next.set(taskId, action)
  return next
}

export function prependUniqueActivity(current, activity) {
  return [activity, ...current.filter((entry) => entry.id !== activity.id)]
}

export function mergeRecentActivities(current, recent) {
  const byId = new Map([...recent, ...current].map((activity) => [activity.id, activity]))
  return [...byId.values()].sort((left, right) => right.id - left.id)
}
