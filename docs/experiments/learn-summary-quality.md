# LEARN summary quality experiment scaffold

Status: Scaffold only. No results are claimed.

# Goal

Evaluate whether LEARN summaries are useful, faithful to the source, and easy to approve after editing.

# Dataset

Use user-approved sample lecture documents only. Include at least one PDF, DOCX, Markdown, and plain text file. Exclude sensitive records unless the environment has an explicit retention and deletion policy.

# Procedure

1. Upload a source document with `LANGUAGE_MODEL_PROVIDER=fake` and record the deterministic baseline.
2. Upload the same source with `LANGUAGE_MODEL_PROVIDER=openai`.
3. Have a reviewer compare source references, missing concepts, invented claims, title quality, and edit effort.
4. Record whether the reviewer would approve, reject, or edit before approval.

# Rubric

| Dimension | Question |
| --- | --- |
| Faithfulness | Are claims supported by cited sections/pages? |
| Coverage | Are the important concepts from the lecture present? |
| Clarity | Would a student understand the generated notes? |
| Actionability | Are takeaways and review questions useful for studying? |
| Edit effort | How much work was needed before approval? |

# Output

Store anonymized notes, configuration, provider, model name, document type, and reviewer decision. Do not store raw lecture documents in this experiment file.
