# Checkpoints

Success states saved as git tags. Use `git checkout tags/<name>` to return.

---

| Tag | Commit | Description |
|---|---|---|
| `v0-success-base` | `70eb368` | Working 8-scene flow: interview refactor, max_tokens 4096, pregen cache empty-reply guard, scene readability prompt, debug logging, track system |
| `v1-blank-screen-fixed` | `edb00ba` | Choice click blank screen fixed: positional lookup (CID_IDX) instead of fragile ID string match. Non-deterministic model output (temp=0.8) no longer breaks choice buttons. Full end-to-end working. |
