# v0.22 POC 2 correction
User approved the diagnosed posting-entries fixes and clearer human answers.
- Replace equal generic-keyword weighting with focused topic/action weighting; retain identifier-sensitive exact release comparisons and identity-first video lookup.
- Add PostgreSQL English stemming lane for title/topic phrases (posting/posted), preserving literal evidence. No global extraction/embedding changes.
- Follow-up accepts explicit revised retrieval_keywords; independently derive focused terms from verifier queries if absent. Fresh evidence displaces weak retained optional evidence while keeping citation IDs stable.
- Collapse exact duplicate source bodies for reading slots, keep path/provenance diagnostics. Never merge distinct revision texts just because names match.
- Answers: direct response, numbered steps where useful, short important notes, human-readable source names and supporting quotations. Full provenance/diagnostics remain in exported JSON.
- Regression: captured failed search terms + actual previously retrieved original target article, generic PDF duplicates, alternate wording, unchanged video/Woodgrove checks; real PostgreSQL stemming and host output checks. No answer/path hardcoding.
- No database reset, new embedding model, new schema or POC 1 workflow change.
