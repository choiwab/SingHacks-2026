# Three-Screen Simplification Record

## Baseline

The previous shipping UI and backend contained 3,782 raw lines across `app/domain.py`, `app/main.py`, and the three static interface files.
It distributed one RM decision across six interface stages.
The baseline had 12 passing tests, clean Ruff checks, and a browser-tested end-to-end path.

## Structural target

The target is three screens, one evidence drawer, one offline pipeline, and one review endpoint.
The specialist council, exposure map, rehearsal, action planner, and connector payload wall are removed as separate subsystems.
Their useful signals are consolidated into the pre-read, scenario, and workflow strip.

## Measurement

The final comparison uses raw lines for the same five shipping files plus the pipeline module.
Tests and generated JSON are reported separately.
No formatter packing or measuring-rule change is used to create the reduction.

## Verification

The final milestone must pass Ruff, pytest, JavaScript syntax checking, desktop and mobile browser flows, and an accessibility audit.

## Final result

Shipping code fell from 3,782 raw lines to 2,509, a 33.7% reduction.
The three interface files fell from 3,106 raw lines to 1,545, a 50.3% reduction.
The Python backend grew from 676 raw lines to 964 because it now ranks all 20 clients, persists reviews, and precomputes two scenarios instead of serving one hard-coded case.

The reduction is entirely structural.
No lines were packed, no documentation was removed to change the count, and generated JSON is excluded from both measurements.
