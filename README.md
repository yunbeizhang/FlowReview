<div align="center">

# FlowReview

### Deny Without Disabling: Safety Evaluation and Control for Multi-Agent Systems

Yunbei Zhang · Saiyue Lyu · Janet Wang · Yingqiang Ge · Jiang Guo · Jihun Hamm · Chandan K. Reddy

[![Website](https://img.shields.io/badge/Project-Website-4E6FA8)](https://yunbeizhang.github.io/FlowReview/)
[![Code](https://img.shields.io/badge/GitHub-Code-24292F?logo=github)](https://github.com/yunbeizhang/FlowReview)
[![Data](https://img.shields.io/badge/Evaluation-Data-3F7D58)](data/)

</div>

Multi-agent systems combine information to solve tasks. The same process can turn individually admissible contributions into an unauthorized action. **FlowReview measures and controls these composed information flows, blocking unauthorized use while preserving authorized capabilities.**

![Composition across agents](assets/teaser.png)

Our work introduces **paired policy evaluation** and connects three review capabilities: **object resolution, permission ranking, and deterministic enforcement**.

![FlowReview overview](assets/pipeline.png)

## Main results

![Capability ladder: selective correctness increases while denied disclosure decreases](assets/results-ladder.png)

**Safety without disabling authorized use.** Object binding and deterministic enforcement raise selective correctness from 0% to 99.6% and reduce verbatim disclosure to 0% in the pooled 24-round evaluation.

![Controlled comparisons of object binding, deterministic enforcement, and global composition review](assets/results-mechanisms.png)

**Three complementary capabilities.** The panels compare (a) class-only with object-bound review, (b) model review with deterministic enforcement after detection, and (c) local with global resolution under composition. Gray marks the baseline and blue the added control. Each panel uses its own scale and evaluation set.

## Quickstart

```bash
git clone https://github.com/yunbeizhang/FlowReview.git
cd FlowReview
uv sync
```

## Run with a model API

**OpenAI**

```bash
export OPENAI_API_KEY="your-key"
uv run flowreview run --suite assembly --model gpt-4.1-mini --output runs/assembly
```

**Claude / Anthropic**

```bash
export ANTHROPIC_API_KEY="your-key"
uv run flowreview run --suite assembly --provider anthropic --model claude-sonnet-4-5 --output runs/claude
```

**Local model server**

Use the model name exposed by your server and set its base URL:

```bash
export OPENAI_API_KEY="local"
uv run flowreview run --suite assembly --model your-model \
  --base-url http://localhost:8000/v1 --token-parameter max_tokens --output runs/local
```

<details>
<summary><b>Amazon Bedrock</b></summary>

```bash
uv sync --extra bedrock
export AWS_PROFILE="your-profile"
uv run --extra bedrock flowreview run --suite assembly --provider bedrock \
  --model your-bedrock-model-id --region us-east-1 --output runs/bedrock
```

</details>

## Choose an evaluation

| `--suite` | Evaluation |
| --- | --- |
| `permission` | Permission-specialist evaluation |
| `assembly` | Model and runtime object assembly |
| `policy-update` | Recovery after a policy change |
| `agentdojo` | AgentDojo tool-use transfer |

The default selects one complete comparison. Use `--limit 0` for the full split and `--split development` for development inputs. The default split is `confirmation`. Add `--dry-run` to preview the selection. Agents use separate model calls. `--model` selects the model used for the run.

For AgentDojo, install its extra first:

```bash
uv sync --extra agentdojo
uv run --extra agentdojo flowreview run --suite agentdojo --model gpt-4.1-mini --output runs/agentdojo
```

The [dataset](data/) includes scenarios, governed objects, policies, agent assignments, and tool-use tasks for these evaluations.

## Outcomes

**D** measures denied use, **A** measures required authorized use, and **C = (1 − D)A** measures their joint success per evaluation unit. AgentDojo reports attack-target commits and task utility.

## Inspect results

```bash
uv run flowreview inspect runs/assembly
```

Each run saves `summary.json` and per-unit observations in its output directory.
