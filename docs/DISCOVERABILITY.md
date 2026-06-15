# Discoverability checklist

This note captures the GitHub/Google-facing setup for making Probity easier to
find when people search for agent evaluation, AI coding agents, false-green
testing, and deterministic reliability checks.

## Principle

Use the language real users and AI-search systems are likely to ask for, but do
not keyword-stuff. The top of the README should answer four questions quickly:

- who has this problem;
- what failure mode Probity targets;
- what method it uses;
- what a user can run in five minutes.

Likely search intents:

- agent reliability methodology;
- AI coding agents;
- false-green testing;
- deterministic checker;
- agent evaluation;
- CI for coding agents;
- test tampering;
- claim vs evidence;
- reproducible audit;
- Codex CLI reliability testing;
- Claude Code reliability testing;
- coding agent false completion;
- agent self-report vs checker evidence.

The wording must still stay inside `PUBLIC_CLAIMS.md`. Discoverability never
overrides evidence boundaries.

## Repository title and description

Recommended GitHub repository description:

```text
Agent reliability methodology for false-green testing of AI coding agents.
```

Alternative descriptions:

```text
Evidence-based reliability testing for AI coding agents.
```

```text
Claim -> evidence -> verdict for coding-agent reliability audits.
```

Avoid:

- "first";
- "only";
- "guarantees correctness";
- "kills hallucinations";
- "best agent benchmark";
- model-ranking language.

## README title

Recommended H1:

```markdown
# Probity: Agent Reliability Methodology for False-Green Testing
```

Why: it keeps the brand name but also names the category and the problem.
Google Search Central recommends descriptive, concise titles and warns against
keyword stuffing. GitHub README headings are also visible page text and anchor
targets.

## Topics

GitHub topics help people explore repositories by purpose, subject area,
community, and language. Use no more than 20.

Recommended topics:

```text
ai-agents
coding-agents
agent-evaluation
agent-reliability
llmops
software-testing
ci
test-automation
developer-tools
deterministic-testing
reliability-testing
false-green
ai-safety
provenance
audit
docker
```

Optional swaps depending on positioning:

```text
llm
agentic-ai
quality-assurance
software-quality
github-actions
```

## Social preview

Create a solid-background 1280x640 PNG with:

- `Probity`
- `Agent reliability methodology`
- `False-green testing for AI coding agents`
- a small `claim -> evidence -> verdict` line

GitHub's docs recommend at least 640x320, with 1280x640 for best display.

## Backlink / launch strategy

Do not lead with valuation or broad safety claims. Lead with the failure mode:

- "How do you catch AI coding agents that edit tests to pass?"
- "A single green run is not enough evidence."
- "Claim vs evidence for coding agents."

Good launch surfaces:

- Show HN;
- r/programming or r/devops;
- GitHub Discussions in agent/tooling communities;
- X/LinkedIn technical thread;
- README links from related docs and blog posts.

## AI-search answer shape

Write public copy so an AI-search answer can summarize the project without
inventing a broad claim:

```text
Probity is a local, deterministic methodology and harness for testing whether
an AI coding agent's success claim survives registered repo evidence. It is
useful for researchers and engineering teams evaluating false-green,
false-completion, test-tampering, and claim-vs-evidence failures. It can wrap
CLI agents such as Codex CLI, Claude Code, or other subprocess-based tools.
```

Avoid content that makes the answer engine infer model ranking, uniqueness,
or broad hallucination elimination.

## Sources

- GitHub Docs, repository topics:
  <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>
- GitHub Blog, Introducing Topics:
  <https://github.blog/news-insights/product-news/introducing-topics/>
- GitHub Docs, social preview:
  <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview>
- Google Search Central, title links:
  <https://developers.google.com/search/docs/appearance/title-link>
