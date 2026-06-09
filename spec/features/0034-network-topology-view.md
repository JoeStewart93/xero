# F0034: Network Topology View

## Metadata
| Field | Value |
|---|---|
| ID | F0034 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0030, F0024 |

## Summary
Interactive network map visualization showing asset relationships, subnet boundaries, beacon positions, and compromised host adjacency using a graph layout engine.

## Requirements
- FR-08: Map View of network topology and compromised hosts
- Graph nodes: assets; edges: subnet adjacency, beacon reachability
- Zoom, pan, and node click for asset detail
- Color coding: compromised (beacon), discovered, service
- Export topology as PNG or JSON graph

## Stages

### Stage 1: Graph data API
**Goal:** Endpoint returning nodes and edges for topology.
**Acceptance Criteria:**
- [ ] GET /api/v1/topology returns {nodes, edges} graph structure
- [ ] Nodes include asset id, label, type, ip, status
- [ ] Edges derived from subnet co-membership and scan reachability

### Stage 2: Map component
**Goal:** React graph visualization with d3-force or cytoscape.
**Acceptance Criteria:**
- [ ] Nodes rendered with type-specific icons and colors
- [ ] Zoom and pan controls; fit-to-screen button
- [ ] Click node opens asset detail side panel

### Stage 3: Layout and export
**Goal:** Auto-layout and export capabilities.
**Acceptance Criteria:**
- [ ] Force-directed layout runs on load and re-layout button
- [ ] Export PNG captures current viewport
- [ ] Export JSON downloads raw graph data

## Feature Acceptance Criteria

- [ ] Topology map renders all assets with correct subnet clustering
- [ ] Beacon hosts visually distinct from discovered-only hosts
- [ ] Map handles 200 nodes without UI freeze on lab hardware

## Test Plan

### Unit Tests
- [ ] test_topology_api_graph_shape
- [ ] test_node_color_by_type
- [ ] test_edge_generation_subnet
- [ ] test_layout_engine_positions_nodes
- [ ] test_export_png_generates_blob

### System / Integration Tests
- [ ] Topology API nodes match asset inventory count
- [ ] Add beacon; map updates via WebSocket without full reload
- [ ] Export JSON matches API response structure

### Playwright Tests
- [ ] Network map page renders graph with asset nodes
- [ ] Click node opens asset detail side panel
- [ ] Zoom and pan controls work smoothly
- [ ] Export PNG downloads image file
