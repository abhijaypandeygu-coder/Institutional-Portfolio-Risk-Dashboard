# M04.02 Taxonomy & Bitemporal Classification Guide

## 1. Multi-Scheme Coexistence
Different portfolio managers, factor models, and regulatory frameworks rely on distinct classification conventions. M04.02 supports independent taxonomy schemes:
- **Global Standards:** GICS, ICB.
- **Regional Schemes:** Indian sector groupings (e.g. NSE sectoral indices).
- **Internal / Quantitative Factor Schemes:** Proprietary clustering.
- Multiple active schemes can be attached to the same instrument simultaneously without overwriting or conflicting with one another.

---

## 2. Sector-Industry Consistency Rules
- A node of type `INDUSTRY` must always define a parent `SECTOR`.
- When assigning a sector and industry to an instrument:
  - The sector node and industry node must belong to the exact same scheme and scheme version.
  - The industry node's `parent_node_id` must match the assigned sector's `node_id`.
  - Violations immediately trigger an HTTP `400 BAD REQUEST` and are rejected.

---

## 3. Bitemporal Point-In-Time Analytics
Historical portfolio attribution, factor returns, and sector concentration must not suffer from look-ahead bias:
- **Valid Time ($T_V$):** The period $[V_{\text{from}}, V_{\text{to}})$ during which the company operated within that sector in the real world.
- **Transaction Time ($T_R$):** The instant $R_{\text{recorded}}$ when the analyst or data feed entered the classification into the dashboard database.
- A point-in-time lookup filters records satisfying:
  $$V_{\text{from}} \le T_V < V_{\text{to}} \quad \text{and} \quad R_{\text{recorded}} \le T_R$$
- Reclassifications (e.g. conglomerate spin-offs or cloud migrations) bump `assignment_version` and preserve the entire prior history.

