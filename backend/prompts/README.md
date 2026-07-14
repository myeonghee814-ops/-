# prompts/

Home for LLM prompt templates used by future features (paper summarization,
cross-paper comparison, Q&A over abstracts, etc.).

Prompts are kept as data separate from `services/`, so they can be edited,
versioned, and unit-tested without touching business logic — and so a
future prompt-tuning workflow doesn't require a code deploy.

No prompts exist yet; this directory is scaffolding for when the
summarization/comparison features are implemented.
