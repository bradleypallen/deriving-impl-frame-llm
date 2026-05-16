# Stop-sign benchmark

Formalization of Simonelli's GPT-4.1 stop-sign dialogue (Example 1 of `revised.tex`) as a single-analyst RSR-targeted benchmark.

## Target inference

`<{sa}, {ra}>` — "a is a stop sign implies a is red".

## Items

| id    | premises          | conclusions | analyst verdict | kind                 |
|-------|-------------------|-------------|-----------------|----------------------|
| row-0 | {sa}              | {ra}        | good            | base inference       |
| row-1 | {sa, n}           | {ra}        | good            | irrelevant addition  |
| row-2 | {sa, nr, n}       | {ra}        | good            | irrelevant addition  |
| row-3 | {sa, ba}          | {ra}        | bad             | defeater             |

The bearers are: `sa` ("a is a stop sign"), `ra` ("a is red"), `n` ("it is nighttime"), `nr` ("a is not made with reflective material"), `ba` ("a has been painted blue").

## Validate

```
infereval validate examples/stop_sign/benchmark.json
```
