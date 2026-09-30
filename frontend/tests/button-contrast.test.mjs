import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const css = readFileSync(new URL("../src/style.css", import.meta.url), "utf8")

function blockFor(pattern) {
  const match = css.match(pattern)
  assert.ok(match, `expected CSS block ${pattern}`)
  return match[1]
}

function variablesFrom(block) {
  return Object.fromEntries([...block.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((match) => [match[1], match[2].trim()]))
}

function resolve(value, variables) {
  const match = value.match(/^var\((--[\w-]+)\)$/)
  return match ? resolve(variables[match[1]], variables) : value
}

function luminance(color) {
  const source = color.slice(1)
  const hex = source.length === 3 ? [...source].map((part) => part + part).join("") : source
  const rgb = hex.match(/../g).map((part) => Number.parseInt(part, 16) / 255)
  const linear = rgb.map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
}

function contrast(foreground, background) {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return (values[0] + 0.05) / (values[1] + 0.05)
}

const lightTheme = variablesFrom(blockFor(/:root\s*\{([^}]+)\}/))
const darkTheme = {
  ...lightTheme,
  ...variablesFrom(blockFor(/@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^}]+)\}/)),
}

for (const [name, theme] of [["light", lightTheme], ["dark", darkTheme]]) {
  const mutedStatusContrast = contrast(resolve(theme["--muted"], theme), resolve(theme["--surface"], theme))
  assert.ok(mutedStatusContrast >= 4.5, `${name} theme status text contrast was ${mutedStatusContrast.toFixed(2)}`)
  for (const color of ["--accent", "--success"]) {
    const iconContrast = contrast(resolve(theme[color], theme), resolve(theme["--surface"], theme))
    assert.ok(iconContrast >= 3, `${name} theme status icon ${color} contrast was ${iconContrast.toFixed(2)}`)
  }
  for (const [background, foreground] of [
    ["--primary-bg", "--primary-fg"],
    ["--primary-hover-bg", "--primary-fg"],
    ["--primary-disabled-bg", "--primary-disabled-fg"],
  ]) {
    const ratio = contrast(resolve(theme[foreground], theme), resolve(theme[background], theme))
    assert.ok(ratio >= 4.5, `${name} theme ${background}/${foreground} contrast was ${ratio.toFixed(2)}`)
  }
}

assert.match(css, /\.task-actions button:not\(\.primary\):not\(\.danger-action\),\s*\.breakdown-heading button\s*\{/)
assert.match(css, /\.task-actions button:not\(\.primary\):not\(\.danger-action\):hover:not\(:disabled\)/)
assert.doesNotMatch(css, /\.task-actions button\s*\{/, "generic task-actions rule must not match primary buttons")

const taskPrimary = blockFor(/\.task-actions \.primary\s*\{([^}]+)\}/)
assert.match(taskPrimary, /background:\s*var\(--primary-bg\)/)
assert.match(taskPrimary, /color:\s*var\(--primary-fg\)/)
assert.match(taskPrimary, /border:\s*1px solid var\(--primary-bg\)/)
assert.match(css, /\.task-actions \.primary:hover:not\(:disabled\)\s*\{[^}]*background:\s*var\(--primary-hover-bg\)[^}]*color:\s*var\(--primary-fg\)/s)
assert.match(css, /\.task-actions \.primary:disabled\s*\{[^}]*background:\s*var\(--primary-disabled-bg\)[^}]*color:\s*var\(--primary-disabled-fg\)/s)
assert.match(css, /\.primary:active,[\s\S]*?transform:\s*translateY\(1px\)/)
assert.match(css, /\.task-actions\s*\{[^}]*flex-wrap:\s*wrap/s, "mobile task actions must wrap rather than clip")
assert.doesNotMatch(css, /button:disabled\s*\{[^}]*opacity:/s, "disabled text must not rely on opacity for its contrast")
assert.doesNotMatch(css, /\.danger-action:disabled,[\s\S]*?opacity:/)
assert.match(css, /\.danger-action:hover:not\(:disabled\)\s*\{[^}]*background:\s*var\(--danger\)[^}]*color:\s*var\(--surface\)/s)
assert.match(css, /\.task-actions \.primary\.small-action\s*\{[^}]*padding:\s*6px 10px/s)

console.log("Primary, task-action, disabled, and danger button contrast passed for light and dark themes")
