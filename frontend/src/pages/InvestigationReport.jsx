import React, { useEffect, useMemo, useState } from "react";
import {
  FileText,
  Download,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";

import Card from "../components/common/Card";
import Badge from "../components/common/Badge";

import {
  getInvestigation,
  getInvestigationEvidence,
  scanEvidence,
  getInvestigationFragments,
  getInvestigationRelationships,
  getReconstructionResults,
  getReconstructionAssessment,
  getReconstructionPriority,
  getReconstructionDna,
  getReconstructionProvenance,
} from "../api";

const asList = (value, key) => {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.[key])) return value[key];
  return [];
};

const formatBytes = (value) => {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "Not available";
  }

  const bytes = Number(value);

  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }

  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(2)} KB`;
  }

  return `${bytes} B`;
};

const formatPercent = (value) => {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "Not available";
  }

  return `${Number(value).toFixed(
    Number(value) % 1 === 0 ? 0 : 1
  )}%`;
};

const statusTone = (status = "") => {
  if (status.includes("Verified")) return "success";
  if (
    status.includes("Inferred") ||
    status.includes("AI")
  ) {
    return "warning";
  }
  if (
    status.includes("Corrupted") ||
    status.includes("Incomplete") ||
    status.includes("Insufficient")
  ) {
    return "danger";
  }
  return "info";
};

function DetailRow({ label, value, mono = false }) {
  return (
    <div className="metric-line">
      <span>{label}</span>
      <b className={mono ? "mono" : ""}>
        {value ?? "Not available"}
      </b>
    </div>
  );
}

export default function InvestigationReport() {
  const [investigation, setInvestigation] =
    useState(null);

  const [evidenceItems, setEvidenceItems] =
    useState([]);

  const [records, setRecords] = useState([]);

  const [fragments, setFragments] =
    useState([]);

  const [relationships, setRelationships] =
    useState([]);

  const [loading, setLoading] =
    useState(true);

  const [refreshing, setRefreshing] =
    useState(false);

  const [error, setError] = useState("");

  const investigationId =
    localStorage.getItem(
      "recoverai_investigation_id"
    ) || null;

  const loadReportData = async () => {
    setError("");

    try {
      if (!investigationId) {
        setInvestigation(null);
        setEvidenceItems([]);
        setRecords([]);
        setFragments([]);
        setRelationships([]);
        return;
      }

      const [
        investigationResult,
        evidenceResult,
        fragmentResult,
        relationshipResult,
      ] = await Promise.all([
        getInvestigation(
          investigationId
        ),
        getInvestigationEvidence(
          investigationId
        ),
        getInvestigationFragments(
          investigationId
        ),
        getInvestigationRelationships(
          investigationId
        ),
      ]);

      const items = asList(
        evidenceResult,
        "evidence"
      );

      const fragmentList = asList(
        fragmentResult,
        "fragments"
      );

      const relationshipList = asList(
        relationshipResult,
        "relationships"
      );

      setInvestigation(
        investigationResult
      );

      setEvidenceItems(items);
      setFragments(fragmentList);
      setRelationships(
        relationshipList
      );

      const builtRecords = [];

      for (const item of items) {
        try {
          const [
            scanResult,
            reconstructionResult,
          ] = await Promise.all([
            scanEvidence(
              item.evidence_id
            ),
            getReconstructionResults(
              item.evidence_id
            ),
          ]);

          const reconstructions =
            asList(
              reconstructionResult,
              "results"
            );

          const latest =
            reconstructions[0] || {};

          let assessment = null;
          let priority = null;
          let dna = null;
          let provenance = null;

          if (
            latest.reconstruction_id
          ) {
            const detailResults =
              await Promise.allSettled([
                getReconstructionAssessment(
                  latest.reconstruction_id
                ),
                getReconstructionPriority(
                  latest.reconstruction_id
                ),
                getReconstructionDna(
                  latest.reconstruction_id
                ),
                getReconstructionProvenance(
                  latest.reconstruction_id
                ),
              ]);

            assessment =
              detailResults[0].status ===
              "fulfilled"
                ? detailResults[0].value
                : null;

            priority =
              detailResults[1].status ===
              "fulfilled"
                ? detailResults[1].value
                : null;

            dna =
              detailResults[2].status ===
              "fulfilled"
                ? detailResults[2].value
                : null;

            provenance =
              detailResults[3].status ===
              "fulfilled"
                ? detailResults[3].value
                : null;
          }

          builtRecords.push({
            evidence: item,
            scan: scanResult,
            reconstructions,
            latest,
            assessment,
            priority,
            dna,
            provenance,
          });
        } catch (itemError) {
          console.error(
            `Unable to load report data for ${item.filename}:`,
            itemError
          );

          builtRecords.push({
            evidence: item,
            scan: null,
            reconstructions: [],
            latest: {},
            assessment: null,
            priority: null,
            dna: null,
            provenance: null,
          });
        }
      }

      setRecords(builtRecords);
    } catch (err) {
      console.error(
        "Unable to load investigation report:",
        err
      );

      setError(
        err.message ||
          "Unable to load investigation report."
      );
    }
  };

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await loadReportData();
      setLoading(false);
    };

    run();
  }, [investigationId]);

  const refresh = async () => {
    setRefreshing(true);
    await loadReportData();
    setRefreshing(false);
  };

  const summary = useMemo(() => {
    const reconstructed =
      records.filter(
        (record) => {
          const status =
            record.latest?.status || "";
          return (
            status.includes(
              "Verified"
            ) ||
            status.includes(
              "Structural Repair"
            ) ||
            status.includes(
              "Reconstruction"
            )
          );
        }
      ).length;

    const partial =
      records.filter(
        (record) => {
          const status =
            record.latest?.status || "";
          return (
            status.includes(
              "Structural"
            ) ||
            status.includes(
              "Partial"
            )
          );
        }
      ).length;

    const unrecoverable =
      records.filter(
        (record) =>
          String(
            record.latest?.status || ""
          ).includes(
            "Unable"
          )
      ).length;

    const uniqueTypes = [
      ...new Set(
        fragments
          .map(
            (fragment) =>
              fragment.file_type
          )
          .filter(Boolean)
      ),
    ];

    const verifiedBytes =
      records.reduce(
        (total, record) =>
          total +
          Number(
            record.latest
              ?.verified_bytes || 0
          ),
        0
      );

    const inferredBytes =
      records.reduce(
        (total, record) =>
          total +
          Number(
            record.latest
              ?.inferred_bytes || 0
          ),
        0
      );

    return {
      evidenceSources:
        evidenceItems.length,
      fragments:
        fragments.length,
      filesDetected:
        records.reduce(
          (total, record) =>
            total +
            Number(
              record.scan
                ?.files_scanned || 0
            ),
          0
        ),
      reconstructed,
      partial,
      unrecoverable,
      uniqueTypes,
      verifiedBytes,
      inferredBytes,
    };
  }, [
    records,
    evidenceItems,
    fragments,
  ]);

  const generatedAt =
    new Date().toLocaleString();

  const printReport = () => {
    window.print();
  };

  const investigationName =
    investigation?.name ||
    "RECOVERAI Investigation";

  const caseId =
    investigation?.investigation_id ||
    investigationId ||
    "Not available";

  if (loading) {
    return (
      <div className="page-intro">
        <div>
          <span className="eyebrow">
            FORENSIC REPORT
          </span>
          <h2>Investigation Report</h2>
          <p>
            Compiling live evidence,
            reconstruction and integrity
            results...
          </p>
        </div>
        <Badge tone="info">
          LOADING
        </Badge>
      </div>
    );
  }

  return (
    <div className="report-page">
      <div className="page-intro report-header">
        <div>
          <span className="eyebrow">
            FORENSIC REPORT
          </span>

          <h2>
            Investigation Report
          </h2>

          <p>
            Evidence-grounded investigation
            summary generated from the
            current RECOVERAI backend state.
          </p>
        </div>

        <div
          className="toolbar report-toolbar"
        >
          <button
            className="secondary-btn"
            onClick={refresh}
            disabled={refreshing}
          >
            <RefreshCw
              size={16}
              className={
                refreshing ? "spin" : ""
              }
            />
            Refresh
          </button>

          <button
            className="secondary-btn"
            onClick={printReport}
          >
            <Download size={16} />
            Print / Save PDF
          </button>
        </div>
      </div>

      {error && (
        <Card>
          <div className="contradiction">
            <AlertTriangle size={18} />
            <div>
              <b>
                Report Data Warning
              </b>
              <p>{error}</p>
            </div>
          </div>
        </Card>
      )}

      <div className="report-document">
        <Card>
          <div className="report-title-block">
            <div>
              <span className="eyebrow">
                RECOVERAI
              </span>
              <h1>
                Digital Evidence
                Investigation Report
              </h1>
              <p>
                AI-Assisted Intelligent Data
                Recovery and Digital Evidence
                Reconstruction
              </p>
            </div>

            <div className="report-status">
              <ShieldCheck size={28} />
              <span>
                EVIDENCE-GROUNDED
              </span>
            </div>
          </div>

          <div className="report-section">
            <div className="card-title">
              Investigation Summary
            </div>

            <div className="report-grid">
              <DetailRow
                label="Investigation"
                value={
                  investigationName
                }
              />

              <DetailRow
                label="Case ID"
                value={caseId}
                mono
              />

              <DetailRow
                label="Evidence Source"
                value={
                  investigation?.source ||
                  "Digital Evidence"
                }
              />

              <DetailRow
                label="Description"
                value={
                  investigation?.description ||
                  "Not provided"
                }
              />

              <DetailRow
                label="Report Generated"
                value={generatedAt}
              />

              <DetailRow
                label="Evidence Sources"
                value={
                  summary.evidenceSources
                }
              />
            </div>
          </div>

          <div className="report-section">
            <div className="card-title">
              Recovery Summary
            </div>

            <div className="telemetry report-metrics">
              <div>
                <small>
                  Evidence Sources
                </small>
                <b>
                  {
                    summary.evidenceSources
                  }
                </b>
              </div>

              <div>
                <small>
                  Fragments Detected
                </small>
                <b>
                  {summary.fragments}
                </b>
              </div>

              <div>
                <small>
                  Files Detected
                </small>
                <b>
                  {summary.filesDetected}
                </b>
              </div>

              <div>
                <small>
                  Reconstructed
                </small>
                <b>
                  {summary.reconstructed}
                </b>
              </div>

              <div>
                <small>
                  Partial
                </small>
                <b>
                  {summary.partial}
                </b>
              </div>

              <div>
                <small>
                  Unrecoverable
                </small>
                <b>
                  {summary.unrecoverable}
                </b>
              </div>
            </div>
          </div>

          <div className="report-section">
            <div className="card-title">
              Evidence Integrity
            </div>

            {evidenceItems.length === 0 ? (
              <p className="muted">
                No evidence records are
                currently attached to this
                investigation.
              </p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Evidence ID</th>
                      <th>File</th>
                      <th>Type</th>
                      <th>Size</th>
                      <th>SHA-256</th>
                      <th>Status</th>
                    </tr>
                  </thead>

                  <tbody>
                    {evidenceItems.map(
                      (item) => {
                        const record =
                          records.find(
                            (entry) =>
                              entry.evidence
                                ?.evidence_id ===
                              item.evidence_id
                          );

                        const status =
                          record?.latest
                            ?.status ||
                          record?.evidence
                            ?.upload_status ||
                          "Stored";

                        return (
                          <tr
                            key={
                              item.evidence_id
                            }
                          >
                            <td className="mono">
                              {
                                item.evidence_id
                              }
                            </td>

                            <td>
                              <b>
                                {
                                  item.filename
                                }
                              </b>
                            </td>

                            <td>
                              {item.file_type ||
                                item.extension ||
                                "Unknown"}
                            </td>

                            <td>
                              {formatBytes(
                                item.size_bytes
                              )}
                            </td>

                            <td
                              className="mono"
                              style={{
                                maxWidth:
                                  260,
                                overflowWrap:
                                  "anywhere",
                              }}
                            >
                              {
                                item.sha256 ||
                                "Not available"
                              }
                            </td>

                            <td>
                              <Badge
                                tone={statusTone(
                                  status
                                )}
                              >
                                {status}
                              </Badge>
                            </td>
                          </tr>
                        );
                      }
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="report-section">
            <div className="card-title">
              Reconstruction Results
            </div>

            {records.length === 0 ? (
              <p className="muted">
                No reconstruction results
                are currently available.
              </p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Evidence</th>
                      <th>Fragments</th>
                      <th>Missing</th>
                      <th>Integrity</th>
                      <th>Confidence</th>
                      <th>Status</th>
                    </tr>
                  </thead>

                  <tbody>
                    {records.map(
                      (record) => {
                        const latest =
                          record.latest ||
                          {};

                        const used =
                          Array.isArray(
                            latest.fragments_used
                          )
                            ? latest
                                .fragments_used
                                .length
                            : Number(
                                latest.fragments_used ||
                                  0
                              );

                        return (
                          <tr
                            key={
                              record.evidence
                                .evidence_id
                            }
                          >
                            <td>
                              {
                                record.evidence
                                  .filename
                              }
                            </td>

                            <td>
                              {used}
                            </td>

                            <td>
                              {formatBytes(
                                latest.missing_bytes
                              )}
                            </td>

                            <td>
                              {formatPercent(
                                latest.structural_integrity
                              )}
                            </td>

                            <td>
                              {formatPercent(
                                latest.recovery_confidence
                              )}
                            </td>

                            <td>
                              <Badge
                                tone={statusTone(
                                  latest.status ||
                                    "Candidate"
                                )}
                              >
                                {latest.status ||
                                  "Candidate"}
                              </Badge>
                            </td>
                          </tr>
                        );
                      }
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="report-section">
            <div className="card-title">
              Fragment Relationship Analysis
            </div>

            <div className="telemetry report-metrics">
              <div>
                <small>
                  Fragments
                </small>
                <b>
                  {fragments.length}
                </b>
              </div>

              <div>
                <small>
                  Relationships
                </small>
                <b>
                  {relationships.length}
                </b>
              </div>

              <div>
                <small>
                  File Types
                </small>
                <b>
                  {summary.uniqueTypes
                    .join(" · ") ||
                    "None detected"}
                </b>
              </div>
            </div>

            {relationships.length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Fragment A</th>
                      <th>Fragment B</th>
                      <th>Relationship</th>
                      <th>Score</th>
                    </tr>
                  </thead>

                  <tbody>
                    {relationships.map(
                      (relationship) => (
                        <tr
                          key={
                            relationship.relationship_id ||
                            `${relationship.fragment_a_id}-${relationship.fragment_b_id}`
                          }
                        >
                          <td className="mono">
                            {
                              relationship.fragment_a_id
                            }
                          </td>

                          <td className="mono">
                            {
                              relationship.fragment_b_id
                            }
                          </td>

                          <td>
                            {
                              relationship.relationship ||
                              "Candidate"
                            }
                          </td>

                          <td>
                            {typeof relationship.relationship_score ===
                            "number"
                              ? formatPercent(
                                  relationship.relationship_score *
                                    100
                                )
                              : "Not available"}
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {relationships.length === 0 && (
              <p className="muted">
                No persisted fragment
                relationships are available
                for this investigation.
              </p>
            )}
          </div>

          <div className="report-section">
            <div className="card-title">
              Evidence Prioritization
            </div>

            {records.length === 0 ? (
              <p className="muted">
                No prioritization results
                are available.
              </p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Evidence</th>
                      <th>Priority</th>
                      <th>Confidence</th>
                      <th>Integrity</th>
                      <th>Reason</th>
                    </tr>
                  </thead>

                  <tbody>
                    {records.map(
                      (record) => {
                        const latest =
                          record.latest ||
                          {};

                        const priority =
                          record.priority
                            ?.priority ||
                          record.priority
                            ?.level ||
                          latest.priority ||
                          "Not available";

                        const reason =
                          record.priority
                            ?.reason ||
                          record.priority
                            ?.reasons ||
                          "Technical prioritization data not available.";

                        return (
                          <tr
                            key={`priority-${record.evidence.evidence_id}`}
                          >
                            <td>
                              {
                                record.evidence
                                  .filename
                              }
                            </td>

                            <td>
                              <Badge
                                tone={
                                  priority
                                    .toLowerCase()
                                    .includes(
                                      "high"
                                    )
                                    ? "danger"
                                    : priority
                                        .toLowerCase()
                                        .includes(
                                          "medium"
                                        )
                                    ? "warning"
                                    : "info"
                                }
                              >
                                {priority}
                              </Badge>
                            </td>

                            <td>
                              {formatPercent(
                                latest.recovery_confidence
                              )}
                            </td>

                            <td>
                              {formatPercent(
                                latest.structural_integrity
                              )}
                            </td>

                            <td>
                              {Array.isArray(
                                reason
                              )
                                ? reason.join(
                                    " · "
                                  )
                                : String(
                                    reason
                                  )}
                            </td>
                          </tr>
                        );
                      }
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="report-section">
            <div className="card-title">
              AI Analysis and Reconstruction
              Reasoning
            </div>

            {records.map(
              (record) => {
                const latest =
                  record.latest ||
                  {};

                const dna =
                  record.dna;

                return (
                  <div
                    key={`ai-${record.evidence.evidence_id}`}
                    style={{
                      borderBottom:
                        "1px solid #e2e8f0",
                      padding:
                        "12px 0",
                    }}
                  >
                    <b>
                      {
                        record.evidence
                          .filename
                      }
                    </b>

                    <DetailRow
                      label="Classification"
                      value={
                        record.scan
                          ?.analysis_mode ||
                        "Backend analysis"
                      }
                    />

                    <DetailRow
                      label="Recovery Status"
                      value={
                        latest.status ||
                        "Candidate"
                      }
                    />

                    <DetailRow
                      label="Evidence DNA Hash"
                      value={
                        dna?.sha256 ||
                        record.evidence
                          .sha256 ||
                        "Not available"
                      }
                      mono
                    />

                    <p className="muted">
                      Relationship and
                      reconstruction
                      conclusions are
                      represented as
                      candidate,
                      confidence-based
                      technical findings.
                      They are not treated as
                      absolute certainty.
                    </p>

                    {latest.status ===
                      "AI-Inferred Reconstruction" && (
                      <div className="contradiction">
                        <AlertTriangle
                          size={17}
                        />
                        <div>
                          <b>
                            INFERRED — NOT
                            VERIFIED ORIGINAL
                            DATA
                          </b>
                          <p>
                            Inferred content must
                            not be represented as
                            authentic recovered
                            forensic evidence.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                );
              }
            )}
          </div>

          <div className="report-section">
            <div className="card-title">
              Chain of Custody / Processing
              Timeline
            </div>

            <div className="provenance">
              {[
                "Evidence acquired",
                "Evidence hashed",
                "Evidence stored",
                "Evidence scanned",
                "Fragments extracted",
                "Fragment relationships analyzed",
                "Reconstruction evaluated",
                "Integrity assessed",
                "Evidence prioritized",
                "Report generated",
              ].map((event, index) => (
                <div key={event}>
                  <i />
                  {event}
                  {index < 9 && (
                    <span>›</span>
                  )}
                </div>
              ))}
            </div>

            <p className="muted">
              The timeline describes
              processing stages represented by
              the current RECOVERAI workflow. It
              does not assert an external legal
              chain-of-custody record unless such
              records are actually stored by the
              backend.
            </p>
          </div>

          <div className="report-section report-disclaimer">
            <CheckCircle2 size={18} />

            <div>
              <b>
                Forensic Interpretation Note
              </b>

              <p>
                Recovery confidence and
                prioritization are technical
                assessments produced by the
                system. A detected signature,
                reconstructed structure or
                AI-inferred content must not be
                treated as proof of original data
                unless the underlying evidence
                supports that conclusion.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <style>{`
        .spin {
          animation: recoverai-spin 0.9s linear infinite;
        }

        @keyframes recoverai-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        @media print {
          .report-toolbar,
          .toolbar {
            display: none !important;
          }

          .report-page {
            background: #fff !important;
          }

          .report-document {
            margin: 0 !important;
          }

          .report-document > .card {
            box-shadow: none !important;
            border: 0 !important;
          }
        }
      `}</style>
    </div>
  );
}

