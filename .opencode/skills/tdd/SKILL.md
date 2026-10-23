---
name: tdd
description: Red-green-refactor, one vertical slice at a time. Use when building features or fixing bugs, especially in the Compiler, validator and Route simulator.
---

Build one **vertical slice** at a time. A slice is one behaviour, end to end.

1. Confirm the interface change and the behaviours to test.
2. Write one test. Run it. It goes **red** for the right reason.
3. Write the least code that turns it green.
4. Repeat from 2 for the next behaviour.
5. Refactor while green. Look for deepening: fold shallow modules into a deep one with a thin interface.

## Seams

- **Compiler**: a **Golden test**. Fixture **Flow** in, exact XML out. One fixture per **Port** path.
- **Route simulator**: assert the node path for given destination and time.
- Validator: assert the error names the node id and port.
- ESL client: fake the socket. Fake only this system boundary.

Test through the public interface and assert behaviour. A test survives a refactor when it never names a private function.
