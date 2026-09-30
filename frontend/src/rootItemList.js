export function toggleExpandedRoot(expandedRootIds, rootId) {
  const next = new Set(expandedRootIds)
  if (next.has(rootId)) next.delete(rootId)
  else next.add(rootId)
  return next
}

export function isExpandedRoot(expandedRootIds, rootId) {
  return expandedRootIds.has(rootId)
}

export function removeRootAndChildren(tasks, rootId) {
  const removedIds = new Set([
    rootId,
    ...tasks.filter((task) => task.parent_id === rootId).map((task) => task.id),
  ])
  return tasks.filter((task) => !removedIds.has(task.id))
}
