export function revealInvalidField(documentRef, field) {
  const element = documentRef.querySelector(`[data-validation-field="${field}"]`)
  if (!element) return null
  element.scrollIntoView({ behavior: "smooth", block: "center" })
  element.focus({ preventScroll: true })
  return element
}
