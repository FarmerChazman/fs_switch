---
name: diagnosing-bugs
description: Disciplined loop for hard bugs: wrong routing, silent calls, stale config, missing live events. Use when a bug resists a first guess.
---

Build a feedback loop that goes **red** on this bug before anything else. Then minimise, hypothesise, instrument, fix, regression-test. Each phase ends before the next starts.

## Loops, cheapest first

1. **Golden test** or **Route simulator** reproduces it at graph level.
2. Replay the captured xml-curl POST body against the handler.
3. Observe the switch: `xml_locate dialplan`, `show channels`, `sofia status`, `sofia global siptrace on`.
4. Watch the **Listener**: confirm the ESL event arrives, then confirm `fs_switch_call` or `fs_switch_agent` is published.

## Rules

- Commands go through the ESL whitelist. Ask me before adding one.
- Minimise to the smallest **Flow** that stays red.
- State one hypothesis, predict what an instrument will show, then read it.
- Turn the red loop into a permanent test before you call it fixed.

Done when the red test is green and a new test guards the cause.
