export function filterCollegeOptions(options, query) {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  if (!normalizedQuery) return options
  return options.filter((option) => option.name.toLocaleLowerCase().includes(normalizedQuery))
}

export function moveCollegeActiveIndex(currentIndex, direction, optionCount) {
  if (optionCount === 0) return -1
  if (direction === "down") return currentIndex < 0 ? 0 : (currentIndex + 1) % optionCount
  return currentIndex < 0 ? optionCount - 1 : (currentIndex - 1 + optionCount) % optionCount
}

export function collegeMenuPlacement(viewportHeight, top, bottom) {
  const spaceAbove = Math.max(0, top - 8)
  const spaceBelow = Math.max(0, viewportHeight - bottom - 8)
  const opensAbove = spaceBelow < 190 && spaceAbove > spaceBelow
  return {
    opensAbove,
    maxHeight: Math.min(280, opensAbove ? spaceAbove : spaceBelow),
  }
}
