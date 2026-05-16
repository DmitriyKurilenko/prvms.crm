import type { Directive, DirectiveBinding } from 'vue'

/**
 * v-responsive-table
 *
 * Turns a PrimeVue DataTable into a stacked-card layout on phones
 * (≤ 767px, see the `.rt-cards` rules in styles/main.css).
 *
 * It is PrimeVue-class-agnostic: it works off the semantic table DOM
 * (`thead > tr > th`, `tbody > tr > td`) so a PrimeVue minor upgrade
 * cannot break it. The directive only:
 *   1. tags the table root with `.rt-cards` (CSS hook),
 *   2. copies every column header text into the matching `td[data-label]`
 *      so the card layout can show "Label: value",
 *   3. marks the empty-message / colspan row with `.rt-empty-row` so it
 *      stays a single centered block instead of a malformed card.
 *
 * Re-sync triggers:
 *   - Vue `updated` hook (parent re-render / data change),
 *   - a MutationObserver on the table subtree (PrimeVue-internal sort,
 *     pagination and async row rendering that bypass the parent update).
 *
 * No feedback loop: the observer watches `childList` only; the directive
 * mutates element *attributes* (`data-label`, class), which are not
 * observed.
 */

const HEADER_SEL = 'thead > tr:first-child > th'
const ROW_SEL = 'tbody > tr'

function syncTable(root: HTMLElement): void {
  const table = root.matches('table') ? (root as HTMLTableElement) : root.querySelector('table')
  if (!table) return

  const headers = table.querySelectorAll<HTMLTableCellElement>(HEADER_SEL)
  const labels: string[] = []
  headers.forEach((th) => {
    // PrimeVue wraps the header label in nested spans; textContent collapses
    // them. Sort indicators are <svg> (no text) so trimming is enough.
    labels.push((th.textContent || '').replace(/\s+/g, ' ').trim())
  })

  table.querySelectorAll<HTMLTableRowElement>(ROW_SEL).forEach((tr) => {
    const cells = Array.from(tr.children).filter(
      (c): c is HTMLTableCellElement => c.tagName === 'TD',
    )

    // Empty-message / loading row: a single cell spanning all columns.
    const spanned = cells.length === 1 && cells[0].hasAttribute('colspan')
    if (spanned || cells.length === 0) {
      tr.classList.add('rt-empty-row')
      return
    }
    tr.classList.remove('rt-empty-row')

    cells.forEach((td, i) => {
      td.setAttribute('data-label', labels[i] ?? '')
    })
  })
}

const observers = new WeakMap<HTMLElement, MutationObserver>()
const frames = new WeakMap<HTMLElement, number>()

function scheduleSync(root: HTMLElement): void {
  const pending = frames.get(root)
  if (pending != null) cancelAnimationFrame(pending)
  frames.set(
    root,
    requestAnimationFrame(() => {
      frames.delete(root)
      syncTable(root)
    }),
  )
}

export const responsiveTable: Directive<HTMLElement, unknown> = {
  mounted(el: HTMLElement, _binding: DirectiveBinding<unknown>) {
    el.classList.add('rt-cards')
    syncTable(el)

    const observer = new MutationObserver(() => scheduleSync(el))
    observer.observe(el, { childList: true, subtree: true })
    observers.set(el, observer)
  },
  updated(el: HTMLElement) {
    scheduleSync(el)
  },
  unmounted(el: HTMLElement) {
    observers.get(el)?.disconnect()
    observers.delete(el)
    const pending = frames.get(el)
    if (pending != null) cancelAnimationFrame(pending)
    frames.delete(el)
  },
}

export default responsiveTable
