# The writeup

A Kaggle Writeup, **3,000 words maximum**, original and unpublished. Draft here in Markdown, then paste it into the
Kaggle Writeup (or attach an arXiv-style PDF through the Public Project Link).

Required parts (from the rules): title and subtitle, abstract, introduction, research description (methods and
experiments), related work and citations.

## Working outline and word budget (about 3,000)

| Section | Words | Content |
|---|---|---|
| Title and subtitle | - | e.g. "When Does a Code Graph Help a Small Coding Agent? A counterfactual test of externalized memory" |
| Abstract | 150 | The question, the design, the three answers |
| 1. Introduction | 400 | Graph tools are everywhere; nobody has shown when they help or whether agents rely on them |
| 2. Setup | 350 | Gemma 4 31B QAT, the harness, 129 tasks, graphs and embeddings |
| 3. When structure helps (Q1) | 400 | The offline map: graph distance vs search rank |
| 4. What structure adds (Q2) | 700 | The counterfactual arms, readership, localization, resolve rate |
| 5. Teaching the model to use it (Q3) | 500 | The skill baseline, the LoRA, reliance before and after, the leaderboard number |
| 6. Related work | 300 | Code Isn't Memory, LocAgent, Talk like a Graph, KG-LLM-Bench, knowledge-conflict work |
| 7. Limitations | 200 | One model, four public repositories, compute budget |

Figures: (1) the Q1 map; (2) the arm-by-outcome plot with readership; (3) reliance before and after training.
