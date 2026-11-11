# Adaptive ERag — current system diagram (TrueAdaptive, tuned config, 2026-11-11)

Mermaid flowchart of the tuned system (`configs/erag_trueadaptive_tuned.yaml`)
as it runs today, including the H12 contested-resolution step now in A/B
(Phase 2.5, flagged off by default). Render with any Mermaid renderer
(mermaid.live, GitHub, VS Code preview).

```mermaid
flowchart TD
    Q["Question\n+ HotpotQA distractor corpus"] --> RET["Retrieve\nBM25, k=3"]

    subgraph HOP["Hop loop — max 2 hops"]
        RET --> POOL["Pool\n(cap 12 passages)"]
        POOL --> DRAFT["Draft answer\nLLM, temp 0"]
        DRAFT --> SC{"Fast Path?\nno gaps & min_eff ≥ 0.8"}
        SC -->|yes| C0A["c0 = min_eff\nSC skipped"]
        SC -->|no| SC2["Sequential SC\nM=1→3, stop on majority\nor ΔH < 0.05"]
        SC2 --> C0B["c0 = SC consensus"]
        C0A --> EXT
        C0B --> EXT
        EXT["Claim extraction\nincremental, max 8\nquestion-grounded"] --> GRAPH["Belief graph + NLI\ncross-encoder verifies each claim\nstatus: supported / contradicted / unresolved"]
        GRAPH --> MEMR["Memory read\nBeliefMemory — OFF\nenabled: false"]
        MEMR --> POL{"Hop 0?\nLearned continuation policy\nlogistic regression, τ=0.05"}
        POL -->|STOP| FINAL
        POL -->|CONTINUE| GAP["Gap selection\nEIG direct, θ_gap 0.6\nweakest claim"]
        GAP --> SAT{"Pool saturated?\nlen ≥ 12"}
        SAT -->|yes| FINAL
        SAT -->|no| TRET["Targeted retrieve\n+ new passages to pool"]
        TRET --> POOL
    end

    subgraph FINAL["Final read"]
        DRAFT2["Loop draft"] --> RR{"Re-read trigger?"}
        RR -->|draft unknown| RRU["Grounded re-read\nunknown"]
        RR -->|draft disagrees\nwith answer claim| RRD["Grounded re-read\ndisagree"]
        RR -->|agrees, but graph\ncontested| RRC["Contested re-read — H12\nflagged, in A/B now\nagreeing vs disagreeing claims"]
        RR -->|agrees, uncontested| KEEP["Keep draft"]
        RRU --> ANS
        RRD --> ANS
        RRC --> ANS
        KEEP --> ANS
        ANS["Final answer = draft\nor re-read answer"] --> ABST{"Abstain?\nanswer_claim eff < θ_abs 0.5"}
        ABST -->|yes| UNK["Answer: unknown"]
        ABST -->|no| OUT["Answer: draft"]
    end

    POL -.->|hop 1+ static| GAP
    GRAPH -.->|post-hop resample: never| FINAL
    MEMR -.->|memory write — OFF| MEMW["Memory write\nsurprise-gated — OFF"]

    OUT --> TRACE["Output row\nanswer, draft, em/f1, llm_calls,\ncache_hits, recall, trace, policy"]
    UNK --> TRACE

    style MEMR fill:#eee,stroke:#999,stroke-dasharray: 5 5
    style MEMW fill:#eee,stroke:#999,stroke-dasharray: 5 5
    style RRC fill:#fff2cc,stroke:#d9a400
```

## Notes

- **Flags that change the shape:** `sc_mode: sequential`, `gate_sc_behind_fast_path: true`,
  `claim_strategy: incremental`, `eig_strategy: direct`, `post_hop_resample: never`,
  `saturation_precheck: true`, `ground_final_read: true`, `max_claims: 8`,
  `theta_abs: 0.5`, `theta_fast: 0.8`, `theta_gap: 0.6`, `max_hops: 2` (ceiling),
  `continuation_policy: configs/continuation_policy_dev.json` (τ=0.05).
- **Off / dashed:** memory read and write are implemented and wired but disabled
  (`memory.enabled: false`) — step 6 verdict "instrument too weak" (fired 1/30).
- **Yellow (H12):** contested-claim resolution, behind `erag.contested_resolution`
  (default false), in Dev-100 A/B as of 2026-11-11.
- **Not in this diagram:** the runner/cache (SQLite cache, one fresh namespace per
  run), the retriever (BM25 first, MiniLM as second check), and the baselines
  (Standard / IRCoT / Adaptive-RAG) the system is compared against.
```

