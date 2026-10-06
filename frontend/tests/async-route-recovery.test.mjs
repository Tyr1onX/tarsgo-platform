import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

import {
  ASYNC_ROUTE_RECOVERY_KEY,
  clearAsyncRouteRecovery,
  handleAsyncRouteResourceError,
  isAsyncRouteResourceError,
} from "../src/asyncRouteRecovery.js"

const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
const fallback = readFileSync(new URL("../src/pages/AsyncRouteLoadError.vue", import.meta.url), "utf8")
const storage = new Map()
const sessionStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: (key) => storage.delete(key),
}

let reloadCount = 0
const reload = () => { reloadCount += 1 }
const failedImport = new TypeError("Failed to fetch dynamically imported module: /assets/TeamPage-old.js")

assert.equal(isAsyncRouteResourceError(failedImport), true)
assert.equal(handleAsyncRouteResourceError(failedImport, { storage: sessionStorage, reload }), "reloading")
assert.equal(reloadCount, 1, "first chunk failure reloads the whole page once")
assert.equal(sessionStorage.getItem(ASYNC_ROUTE_RECOVERY_KEY), "attempted")
assert.equal(handleAsyncRouteResourceError(failedImport, { storage: sessionStorage, reload }), "fallback")
assert.equal(reloadCount, 1, "a second chunk failure cannot start another automatic reload")

const apiError = new Error("Request failed with status code 404")
assert.equal(isAsyncRouteResourceError(apiError), false)
assert.equal(handleAsyncRouteResourceError(apiError, { storage: sessionStorage, reload }), "ordinary")
assert.equal(reloadCount, 1, "ordinary API errors do not reload")
assert.equal(
  handleAsyncRouteResourceError(failedImport, {
    storage: { getItem() { throw new Error("storage unavailable") } },
    reload,
  }),
  "fallback",
  "unavailable session storage falls back instead of risking a reload loop",
)
assert.equal(reloadCount, 1)

clearAsyncRouteRecovery(sessionStorage)
assert.equal(sessionStorage.getItem(ASYNC_ROUTE_RECOVERY_KEY), null, "a successfully loaded lazy page clears the recovery marker")
assert.equal(handleAsyncRouteResourceError(new Error("Loading chunk 42 failed"), { storage: sessionStorage, reload }), "reloading")
assert.equal(reloadCount, 2, "a later deployment can use recovery again after success")

assert.match(app, /function defineLazyPage\([\s\S]*?loadingComponent: LocalPageLoading[\s\S]*?errorComponent: AsyncRouteLoadError/)
assert.match(app, /clearAsyncRouteRecovery\(\)[\s\S]*?return page/)
assert.match(app, /onError\(error, _retry, fail\)[\s\S]*?handleAsyncRouteResourceError\(error\)[\s\S]*?fail\(\)/)

const lazyRoutes = [
  "TeamPage.vue",
  "MemberDetailPage.vue",
  "KnowledgePage.vue",
  "SchoolLeavePage.vue",
  "CampLeavePublicPage.vue",
]
for (const route of lazyRoutes) {
  assert.match(app, new RegExp(`defineLazyPage\\(\\(\\) => import\\(\\"\\./pages/${route}\\"\\)\\)`))
}
assert.match(app, /path === '\/leave'[\s\S]*?<SchoolLeavePage/)
assert.match(app, /path === '\/team'[\s\S]*?<TeamPage/)
assert.match(app, /path === '\/knowledge'[\s\S]*?<KnowledgePage/)

assert.match(fallback, /页面加载失败/)
assert.match(fallback, /可能是版本刚刚更新，请重新加载页面。/)
assert.match(fallback, /<button[^>]*@click="reloadPage"[^>]*>重新加载<\/button>/)
assert.match(fallback, /window\.location\.reload\(\)/)

console.log("Async route recovery, loop protection, fallback, API error isolation, and lazy routes passed")
