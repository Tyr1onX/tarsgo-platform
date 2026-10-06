export const ASYNC_ROUTE_RECOVERY_KEY = "tarsgo:async-route-recovery"

const asyncResourceErrorPatterns = [
  /failed to fetch dynamically imported module/i,
  /loading (?:css )?chunk(?:\s+[\w.-]+)?\s+failed/i,
  /chunkloaderror/i,
  /importing a module script failed/i,
  /error loading dynamically imported module/i,
  /failed to load module script/i,
]

export function isAsyncRouteResourceError(error) {
  const message = error instanceof Error ? error.message : String(error ?? "")
  return asyncResourceErrorPatterns.some((pattern) => pattern.test(message))
}

export function handleAsyncRouteResourceError(
  error,
  { storage, reload = () => window.location.reload() } = {},
) {
  if (!isAsyncRouteResourceError(error)) return "ordinary"

  try {
    const sessionStorage = storage ?? window.sessionStorage
    if (sessionStorage.getItem(ASYNC_ROUTE_RECOVERY_KEY) === "attempted") return "fallback"
    sessionStorage.setItem(ASYNC_ROUTE_RECOVERY_KEY, "attempted")
  } catch {
    // Without a persistent session marker, a reload could form an endless loop.
    return "fallback"
  }

  try {
    reload()
    return "reloading"
  } catch {
    return "fallback"
  }
}

export function clearAsyncRouteRecovery(storage) {
  try {
    const sessionStorage = storage ?? window.sessionStorage
    sessionStorage.removeItem(ASYNC_ROUTE_RECOVERY_KEY)
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }
}
