---
name: grim
claim_type: grim
fields: [mean, n]
---
**grim** - means of integer-valued data (Likert items, counts, ages in whole years, number of correct answers).
Extract one claim per reported mean where the underlying data can only be whole numbers and the sample size of
that exact cell/group is stated. Skip means of continuous measures (reaction times, weights), of transformed or
standardised scores, and estimated/adjusted means (from regression, ANCOVA, mixed models).

- `mean`: the mean as a STRING exactly as printed, keeping trailing zeros (e.g. "3.50", not 3.5)
- `n`: the number of participants contributing to this mean, as a STRING (the group n, not the total N)
- `items` (optional): number of items averaged into the scale score (omit or "1" for single items or sum scores)
- `quote`: verbatim passage from the paper that reports the mean and n

Example: `{"type": "grim", "mean": "5.19", "n": "28", "items": "1", "quote": "participants in the control group (n = 28) reported a mean of 5.19"}`
