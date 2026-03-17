# ExamForge

AI-powered exam generator with Bloom's taxonomy tagging, rubric-based grading, and rich reporting.

## Features

- **Question Generation**: MCQ, short answer, and essay questions from source content
- **Bloom's Taxonomy**: Automatic cognitive-level tagging (Remember through Create)
- **Auto-Grading**: Instant MCQ and short-answer grading
- **Essay Grading**: LLM-based essay evaluation against rubrics
- **Rich Reports**: Terminal-based grade reports with detailed breakdowns

## Installation

```bash
pip install -e .
```

## CLI Usage

```bash
# Generate an exam from content
examforge generate --topic "Cell Biology" --mcq 10 --short 5 --essay 2 --output exam.json

# Grade a submission
examforge grade --exam exam.json --submission answers.json --output results.json

# Display a rich report
examforge report --results results.json
```

## Python API

```python
from examforge.generator.mcq import MCQGenerator
from examforge.generator.bloom import BloomTaxonomy

gen = MCQGenerator()
questions = gen.generate(topic="Photosynthesis", count=5)

for q in questions:
    level = BloomTaxonomy.classify(q)
    print(f"[{level.value}] {q.text}")
```

## Author

Mukunda Katta
