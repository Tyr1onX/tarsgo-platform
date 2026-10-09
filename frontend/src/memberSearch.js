export const UNASSIGNED_TEAM_GROUP = "unassigned"

export function filterMembers(members, query = "", group = "", searchFields = ["name"]) {
  const normalizedQuery = query.trim().toLocaleLowerCase()

  return members.filter((member) => {
    if (group && member.team_group_unknown) return false
    if (group === UNASSIGNED_TEAM_GROUP) {
      if (member.team_group) return false
    } else if (group && member.team_group !== group) {
      return false
    }

    if (!normalizedQuery) return true
    return searchFields.some((field) =>
      String(member[field] ?? "").toLocaleLowerCase().includes(normalizedQuery),
    )
  })
}
