# Daily Report Template

Use topic-based sections, not rigid "Done / In Progress / Tomorrow" structure.
Write naturally — like briefing a colleague, not filling out a form.

## Format

```markdown
@<Name>(<Handle>)

- **<Topic 1>**
  - <Natural language description of what you did, why, key findings>;
    <specific details: numbers, comparisons, links>.
  - <Related doc links if any>
  - Status: <done / in progress / blocked / waiting for xxx>.

- **<Topic 2>**
  - <Description>; <details>.
  - Status: <status>.
```

## Style guide

- Group by work topic, not by completion status
- 1-3 sentences per topic, natural language with inline technical details
- Include specific numbers when available ("2108/3794, 55.6%")
- Attach links (docs, dashboards) directly under the topic
- End each topic with a brief "Status: xxx" tag
- No separate "Key conclusions" / "Risks" / "Tomorrow plan" sections —
  fold important info into the relevant topic description
- Keep it concise: a good daily report is 10-20 lines, not a full page

## Example

```markdown
@Alice(alice)

- **Model training pipeline**
  - Finished data preprocessing for the new dataset (12k samples);
    training script validated with a 100-sample smoke test, loss converges normally.
  - Status: ready to launch full training.

- **Evaluation metric redesign**
  - Old metric had hyperparameter sensitivity issues; new version normalizes
    scores to [0,1] using mean point cloud matching distance.
    Tested on 5 cases, anti-hacking improved significantly.
  - Design doc: https://docs.example.com/eval-v2
  - Status: done, pending review.

- **Cluster job for inference**
  - Submitted 2000 tasks on 8 nodes; currently at 1200/2000 (60%).
    Pose output looks correct, but visualization has a font issue (non-blocking).
  - Status: running.
```
