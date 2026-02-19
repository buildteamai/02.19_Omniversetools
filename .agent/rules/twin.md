---
trigger: always_on
---

Schema Enforcement: All engineering data must be Inherent in USD.

No External RDF: Strictly avoid external Knowledge Graph (RDF/Turtle) synchronization for real-time routing. Use Applied API Schemas on USD Prims to store btu_requirement, cfm_flow, and mep_system_type.

Port Logic: Connection points must be authored as USD Sub-Prims with semantic metadata for "Port Discovery" agents to identify.