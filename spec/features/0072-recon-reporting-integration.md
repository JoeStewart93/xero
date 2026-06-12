# F0072: Recon Reporting Integration

## Metadata
| Field | Value |
|---|---|
| ID | F0072 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0071, F0015.01-AMD |

## Summary
Integrate reconnaissance data into campaign reports. Includes scan summaries, vulnerability findings, asset discovery timeline, and export functionality (PDF, HTML, JSON, CSV).

## Requirements
- Scan summaries in reports
- Vulnerability findings with severity
- Asset discovery timeline
- Export formats: PDF, HTML, JSON, CSV
- Charts/graphs for vulnerability distribution
- Generated PDF, HTML, JSON, and CSV exports are stored as managed artifacts through F0015.01-AMD.

## Report Sections

### 1. Executive Summary
- Total assets discovered
- Total vulnerabilities found
- Severity distribution
- Key findings

### 2. Scan Summary
- Scans performed
- Targets scanned
- Duration and timing
- Tools used

### 3. Asset Inventory
- Hosts discovered
- Services identified
- Domains enumerated
- Cloud resources

### 4. Vulnerability Findings
- CVEs by severity
- Affected services
- Remediation recommendations

### 5. Timeline
- Discovery chronology
- Scan execution order
- Asset creation timestamps

## Export Formats

| Format | Use Case |
| :--- | :--- |
| PDF | Executive reports, printable |
| HTML | Interactive, web-viewable |
| JSON | Raw data, API integration |
| CSV | Spreadsheet analysis |

## Stages

### Stage 1: Report Data Aggregation
**Goal:** Aggregate recon data for reports.
**Acceptance Criteria:**
- [ ] Scan summary aggregation
- [ ] Vulnerability statistics
- [ ] Asset counts by type
- [ ] Timeline data extraction

### Stage 2: Report Generation
**Goal:** Generate reports in multiple formats.
**Acceptance Criteria:**
- [ ] PDF report generation
- [ ] HTML report generation
- [ ] JSON export
- [ ] CSV export

### Stage 3: Visualization
**Goal:** Add charts and graphs.
**Acceptance Criteria:**
- [ ] Vulnerability severity pie chart
- [ ] Asset discovery timeline
- [ ] Scan progress charts

### Stage 4: UI Integration
**Goal:** Display and download reports.
**Acceptance Criteria:**
- [ ] Report generation from UI
- [ ] Format selection
- [ ] Download functionality
- [ ] Preview before download

## Feature Acceptance Criteria

- [ ] Recon data included in campaign reports
- [ ] Export formats work correctly
- [ ] Charts/graphs for vulnerability distribution
- [ ] Executive summary generation

## Test Plan

### Unit Tests
- [ ] test_report_data_aggregation
- [ ] test_pdf_generation
- [ ] test_html_generation
- [ ] test_json_export
- [ ] test_csv_export

### System / Integration Tests
- [ ] Report includes all scan data
- [ ] Vulnerability counts accurate
- [ ] Timeline correct
- [ ] Exports contain expected data

### Playwright Tests
- [ ] Generate report from UI
- [ ] Select export format
- [ ] Download PDF report
- [ ] Report displays correctly

---

*End of Document*
