# Order Book Continuity & M02 Resynchronization Guide

## 1. Sequence Continuity Architecture
In institutional Level 2 depth feeds, incremental order book deltas (`OrderBookDeltaInput`) depend on unbroken causal continuity. Missing even one delta can lead to:
- Ghost liquidity (levels that were cancelled but remain displayed)
- Distorted imbalance and bid-ask spread
- False arbitrage signals

---

## 2. Gap Detection Mechanics
`M03.04.04` validates incoming delta sequences against expected state:
- If `sequence_number == expected_sequence`: Continuous ($\Delta s = 0$).
- If `sequence_number < expected_sequence`: Backwards or duplicate packet (`SEQUENCE_BACKWARDS`).
- If `sequence_number > expected_sequence`: Packet loss / gap (`SEQUENCE_GAP`).

```
Snapshot (seq: 100) -> Delta (seq: 101) -> Delta (seq: 102) -> [DROPPED 103, 104] -> Delta (seq: 105)
                                                                                       ^
                                                                              GAP TRIGGERED (105 > 103)
```

---

## 3. Resynchronization Protocol
When a gap occurs:
1. **Downstream Gating:** The validator sets `has_continuity_break = True`, `is_valid = False`, and immediately revokes metric eligibility:
   - `spread_eligible = False`
   - `imbalance_eligible = False`
   - `depth_eligible = False`
   - `liquidity_eligible = False`
2. **Incident Creation:** Opens a `BookIntegrityIncident` with type `CONTINUITY_BREAK` and severity `CRITICAL`.
3. **Resync Dispatch:** Creates a `BookResynchronizationRequest` specifying `feed_id`, `symbol`, `from_sequence`, and `to_sequence`.
4. **Recovery:** The order book reconstructor consumes an authoritative, full `OrderBookSnapshot` from M02, resetting the baseline sequence and restoring validity.
