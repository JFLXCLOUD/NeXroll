# Flow view review

## Fixed

The initial implementation deliberately reset positions on every drop. It inferred playback order from the horizontal drop position, then replaced all nodes with an automatic layout. Selection/settings updates also rebuilt the layout, and index-based node IDs changed ownership when blocks were inserted or reordered.

- Dragging now changes canvas placement only. Earlier/later buttons explicitly change playback order.
- Stable block IDs keep node identity through insertion, deletion, and reordering.
- Optional `flow_positions` metadata survives sequence sanitization and saving. Simple and Advanced geometry is separate; IF, play, and Otherwise/Skip nodes can all move.
- Auto arrange restores the active mode's layout. Insertion and settings edits no longer reset the viewport.
- Connections have direction arrows. Toolbars show the selected playback step; touch targets, focus outlines, node hover/drag states, and minimap sizing were adjusted.
- Mobile toolbar placement was checked for overlap. The inline insertion menu exposes expanded state and closes on Escape.

Existing backend sequence endpoints store block dictionaries directly, so no schema migration is needed. This remains a sequence editor with conditional branches: connections are derived from playback order, not freely editable graph edges.

## Validation

- 13 focused Flow layout and sequence serialization tests pass.
- Real Chromium mouse interaction in an isolated component harness covers drag/drop, selection, settings edits, List/Flow-style unmount/remount, explicit reorder, save/serialize/reload, conditional branch placement, Auto arrange, and insertion.
- Browser screenshots and overflow/toolbar checks cover 390, 768, and 1440px in light and dark styles, with no page errors. These are viewport checks, not physical-device tests.
- Production frontend compilation succeeds with existing App/Sidebar/dynamicPrerollMotion lint warnings and browser compatibility data warnings.
- Harness, screenshots, and build output are under `.codex-tmp/flow-review/`. The harness simulates save/reload through the actual sequence serializer; it does not exercise a live server/database write.

## Suggested next work

1. Undo/redo for block edits, deletion, ordering, and canvas placement.
2. Fit selected step and remember pan/zoom when switching views, especially for long sequences.
3. Show missing configuration and preview outcomes directly on nodes so the flow explains what will play or be skipped.
4. If free connection editing is desired, define graph validation and playback semantics first; the current executor consumes an ordered list, not an arbitrary graph.
