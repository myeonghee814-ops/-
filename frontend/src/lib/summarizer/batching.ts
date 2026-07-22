import type { Batch, BatchingConfig, ExtractedPaper } from "../../types/summarizer";

/**
 * Greedily groups extracted papers into batches, respecting both the max
 * paper count and the max total estimated tokens per batch. A paper that
 * alone exceeds maxTokensPerBatch is sent as its own single-paper batch
 * rather than being split or summarized further (out of scope for v1).
 */
export function buildBatches(papers: ExtractedPaper[], config: BatchingConfig): Batch[] {
  const batches: Batch[] = [];
  let current: ExtractedPaper[] = [];
  let currentTokens = 0;

  const flush = () => {
    if (current.length === 0) return;
    batches.push({ index: batches.length, papers: current, estimatedTokens: currentTokens });
    current = [];
    currentTokens = 0;
  };

  for (const paper of papers) {
    const wouldExceedCount = current.length + 1 > config.maxPapersPerBatch;
    const wouldExceedTokens =
      current.length > 0 && currentTokens + paper.estimatedTokens > config.maxTokensPerBatch;

    if (wouldExceedCount || wouldExceedTokens) {
      flush();
    }

    current.push(paper);
    currentTokens += paper.estimatedTokens;
  }
  flush();

  return batches;
}
