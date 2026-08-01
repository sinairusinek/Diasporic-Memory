/**
 * DOM Range <-> plain-text character offsets.
 *
 * The standard technique (what rangy and Hypothesis's TextPositionAnchor do):
 * walk the pane's text nodes in document order with a TreeWalker, accumulating
 * textContent.length until the range's boundary node is reached.
 *
 * It is only correct if the rendered DOM emits exactly the pane text and
 * nothing else. Two rules enforce that, and both live outside this file:
 *   - segments.ts renders flat, non-overlapping siblings, so no character is
 *     wrapped twice and none is reordered;
 *   - the pane CSS uses `white-space: pre-wrap` and no ::before/::after
 *     content, so nothing is collapsed or injected.
 * assertPaneIntegrity() below checks the result at runtime.
 */

/**
 * Character offset of a boundary point within `root`'s text content.
 *
 * Measuring with a Range rather than counting nodes by hand handles the case
 * where the boundary lands on an element rather than a text node — which it
 * does whenever the user selects a whole highlighted span, or double-clicks a
 * word that happens to fill one. Range.toString() concatenates exactly the text
 * nodes the walker would visit, so this agrees with offsetsToRange below.
 */
function offsetOfPoint(root: Node, node: Node, nodeOffset: number): number | null {
  try {
    const r = document.createRange();
    r.setStart(root, 0);
    r.setEnd(node, nodeOffset);
    return r.toString().length;
  } catch {
    return null;
  }
}

export function rangeToOffsets(
  root: HTMLElement,
  range: Range
): { start: number; end: number } | null {
  if (!root.contains(range.startContainer) || !root.contains(range.endContainer)) {
    return null;
  }
  const start = offsetOfPoint(root, range.startContainer, range.startOffset);
  const end = offsetOfPoint(root, range.endContainer, range.endOffset);
  if (start === null || end === null) return null;
  return start <= end ? { start, end } : { start: end, end: start };
}

/** Inverse: build a Range for [start, end) so we can scroll to it. */
export function offsetsToRange(
  root: HTMLElement,
  start: number,
  end: number
): Range | null {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let total = 0;
  let startNode: Node | null = null;
  let startOffset = 0;
  let endNode: Node | null = null;
  let endOffset = 0;

  let node = walker.nextNode();
  while (node) {
    const len = node.textContent?.length ?? 0;
    if (!startNode && total + len >= start) {
      startNode = node;
      startOffset = start - total;
    }
    if (!endNode && total + len >= end) {
      endNode = node;
      endOffset = end - total;
      break;
    }
    total += len;
    node = walker.nextNode();
  }
  if (!startNode || !endNode) return null;
  const range = document.createRange();
  range.setStart(startNode, startOffset);
  range.setEnd(endNode, endOffset);
  return range;
}

/**
 * The single check that catches most anchoring bugs.
 *
 * If this ever fails, the rendered DOM is not character-identical to the pane
 * text and every offset computed from a selection is wrong. Dev-only: in
 * production a mismatch is still caught per-save by the slice comparison in
 * TextPane, which refuses rather than storing a bad anchor.
 */
export function assertPaneIntegrity(root: HTMLElement, paneText: string): void {
  const rendered = root.textContent ?? '';
  if (rendered === paneText) return;
  let i = 0;
  while (i < rendered.length && i < paneText.length && rendered[i] === paneText[i]) i++;
  console.error(
    `[annotator] pane DOM does not match pane text.\n` +
      `  rendered ${rendered.length} chars, expected ${paneText.length}\n` +
      `  first difference at ${i}\n` +
      `  rendered: ${JSON.stringify(rendered.slice(Math.max(0, i - 30), i + 30))}\n` +
      `  expected: ${JSON.stringify(paneText.slice(Math.max(0, i - 30), i + 30))}`
  );
}
