# E1 Benchmark Dataset Card

This benchmark contains 100 English SDN intent instructions: 50 original
NetIntent instruction/output pairs and 50 project-authored cases. Semantic gold
is an ordered `IntentProgram`; it is an independent annotation and not an
official NetIntent label. The upstream material retains its MIT license and
pinned repository provenance.

The project-authored cohort intentionally includes ten requests that must be
rejected: three ambiguous, two contradictory, three unknown-entity, and two
unsupported cases. `h9`, `database-server`, and `10.0.0.99` remain outside the
inventory. The benchmark should measure rejection behavior with both the full
10-case denominator and the 2-case unsupported-only denominator.

Gold status: **provisional**. The checked-in annotator artifacts are pipeline fixtures, not evidence of human inter-annotator agreement. Final publication results require two independent annotations and adjudication.

Known limitation: the minimum repeated-run sample is five. Bootstrap intervals
are exploratory, not evidence for strong population inference. Variation labels
are retained for traceability but are not approved for stratified reporting.
