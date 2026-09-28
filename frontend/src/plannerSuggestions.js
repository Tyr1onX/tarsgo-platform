export function plannerSuggestionKey(suggestion) {
  return `${suggestion.title.trim()}\u0000${suggestion.reason.trim()}`
}

export function filterIgnoredPlannerSuggestions(draft, ignoredKeys) {
  draft.suggestions = (draft.suggestions ?? []).filter(
    (suggestion) => !ignoredKeys.has(plannerSuggestionKey(suggestion)),
  )
  return draft
}

export function ignorePlannerSuggestion(draft, index, ignoredKeys) {
  const suggestion = draft.suggestions?.[index]
  if (!suggestion) return
  ignoredKeys.add(plannerSuggestionKey(suggestion))
  draft.suggestions.splice(index, 1)
}

export function plannerSuggestionJoinInstruction(suggestion) {
  return `负责人已确认将“${suggestion.title.trim()}”纳入本次事项。请将其合理融合进当前方案，按照真实责任边界决定是新增 task 还是加入现有 task 的 execution_points / cautions / prerequisites。不要再把它保留为 suggestion。只纳入这一已确认子意图，不要扩展到未确认的相邻用途。`
}