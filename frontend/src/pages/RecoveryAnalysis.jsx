import React, { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Circle,
  LoaderCircle,
  AlertTriangle,
  RefreshCw,
  Network,
  Play,
} from "lucide-react";

import Card from "../components/common/Card";
import ProgressBar from "../components/common/ProgressBar";
import Badge from "../components/common/Badge";
import {
  getInvestigation,
  getInvestigationEvidence,
  getInvestigationFragments,
  getInvestigationRelationships,
  scanEvidence,
  analyzeInvestigationRelationships,
} from "../api";

function formatBytes(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
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
}

function toneForIntegrity(status) {
  if (status === "Structurally Valid") return "success";
  if (
    status === "Corrupted or Incomplete" ||
    status === "Corrupted"
  ) {
    return "warning";
  }
  return "info";
}

export default function RecoveryAnalysis() {
  const [investigation, setInvestigation] = useState(null);
  const [evidenceItems, setEvidenceItems] = useState([]);
  const [activeEvidence, setActiveEvidence] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [fragments, setFragments] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [relationshipRunning, setRelationshipRunning] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const investigationId =
    localStorage.getItem("recoverai_investigation_id") || null;

  const storedActiveEvidence = useMemo(() => {
    try {
      const raw = localStorage.getItem("recoverai_current_evidence");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }, []);

  const loadEvidenceWorkspace = async (evidenceId) => {
    if (!evidenceId) {
      setAnalysis(null);
      setFragments([]);
      setRelationships([]);
      return;
    }

    const [scanResult, fragmentResult, relationshipResult] =
      await Promise.all([
        scanEvidence(evidenceId),
        investigationId
          ? getInvestigationFragments(investigationId)
          : Promise.resolve([]),
        investigationId
          ? getInvestigationRelationships(investigationId)
          : Promise.resolve([]),
      ]);

    setAnalysis(scanResult);

    const fragmentList = Array.isArray(fragmentResult)
      ? fragmentResult
      : fragmentResult?.fragments || [];

    const relationshipList = Array.isArray(relationshipResult)
      ? relationshipResult
      : relationshipResult?.relationships || [];

    setFragments(
      fragmentList.filter(
        (fragment) =>
          !fragment.evidence_id ||
          fragment.evidence_id === evidenceId
      )
    );

    setRelationships(
      relationshipList.filter(
        (relationship) =>
          !relationship.evidence_id ||
          relationship.evidence_id === evidenceId
      )
    );

    localStorage.setItem(
      "recoverai_analysis_result",
      JSON.stringify(scanResult)
    );
  };

  const loadWorkspace = async () => {
    setLoading(true);
    setError("");

    try {
      let currentEvidence = storedActiveEvidence;

      if (investigationId) {
        const [investigationResult, evidenceResult] =
          await Promise.all([
            getInvestigation(investigationId),
            getInvestigationEvidence(investigationId),
          ]);

        setInvestigation(investigationResult);

        const items = Array.isArray(evidenceResult)
          ? evidenceResult
          : evidenceResult?.evidence || [];

        setEvidenceItems(items);

        const preferred =
          items.find(
            (item) =>
              item.evidence_id ===
              currentEvidence?.evidence_id
          ) ||
          items[0] ||
          currentEvidence;

        if (preferred) {
          currentEvidence = preferred;
          setActiveEvidence(preferred);
          localStorage.setItem(
            "recoverai_current_evidence",
            JSON.stringify(preferred)
          );
        }
      } else if (currentEvidence) {
        setActiveEvidence(currentEvidence);
        setEvidenceItems([currentEvidence]);
      }

      if (!currentEvidence?.evidence_id) {
        setAnalysis(null);
        setFragments([]);
        setRelationships([]);
        return;
      }

      await loadEvidenceWorkspace(currentEvidence.evidence_id);
    } catch (err) {
      console.error("Failed to load recovery analysis:", err);
      setError(
        err.message ||
          "Unable to load live recovery analysis."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkspace();
  }, [investigationId]);

  const selectEvidence = async (item) => {
    if (!item?.evidence_id) return;

    setActiveEvidence(item);
    setError("");
    setMessage("");

    localStorage.setItem(
      "recoverai_current_evidence",
      JSON.stringify(item)
    );
    localStorage.removeItem("recoverai_reconstruction_result");

    try {
      setLoading(true);
      await loadEvidenceWorkspace(item.evidence_id);
      setMessage(`${item.filename} is now the active evidence artifact.`);
    } catch (err) {
      setError(err.message || "Unable to load selected evidence.");
    } finally {
      setLoading(false);
    }
  };

  const runAnalysis = async () => {
    if (!activeEvidence?.evidence_id) {
      setError("Select an evidence artifact before running analysis.");
      return;
    }

    setRunning(true);
    setError("");
    setMessage("");

    try {
      await loadEvidenceWorkspace(activeEvidence.evidence_id);
      setMessage("Evidence scan and fragment analysis completed.");
    } catch (err) {
      setError(err.message || "Unable to run evidence analysis.");
    } finally {
      setRunning(false);
    }
  };

  const runRelationships = async () => {
    if (!investigationId) {
      setError("No active investigation is available for relationship analysis.");
      return;
    }

    setRelationshipRunning(true);
    setError("");
    setMessage("");

    try {
      const result = await analyzeInvestigationRelationships(
        investigationId
      );

      const relationshipList = Array.isArray(result)
        ? result
        : result?.relationships || [];

      setRelationships(relationshipList);

      if (activeEvidence?.evidence_id) {
        setRelationships(
          relationshipList.filter(
            (relationship) =>
              !relationship.evidence_id ||
              relationship.evidence_id === activeEvidence.evidence_id
          )
        );
      }

      setMessage(
        result?.message ||
          "Fragment relationship analysis completed."
      );
    } catch (err) {
      setError(
        err.message ||
          "Unable to run fragment relationship analysis."
      );
    } finally {
      setRelationshipRunning(false);
    }
  };

  const scanResults = useMemo(
    () => analysis?.results || [],
    [analysis]
  );

  const detectedFragments = useMemo(() => {
    if (fragments.length) return fragments;

    return scanResults.flatMap(
      (result) => result.detections || []
    );
  }, [fragments, scanResults]);

  const detectedTypes = useMemo(
    () => [
      ...new Set(
        detectedFragments
          .map((fragment) => fragment.file_type)
          .filter(Boolean)
      ),
    ],
    [detectedFragments]
  );

  const bytesScanned = useMemo(
    () =>
      scanResults.reduce(
        (total, result) =>
          total + Number(result.size_bytes || 0),
        0
      ),
    [scanResults]
  );

  const validationSummary = useMemo(() => {
    if (!detectedFragments.length) {
      return {
        completed: false,
        validCount: 0,
        invalidCount: 0,
        unsupportedCount: 0,
        pendingCount: 0,
        averageIntegrity: null,
        verifiedBytes: 0,
        inferredBytes: 0,
      };
    }

    const pending = detectedFragments.filter(
      (fragment) =>
        fragment.structural_integrity === null ||
        fragment.structural_integrity === undefined
    );

    const valid = detectedFragments.filter(
      (fragment) =>
        fragment.integrity_status === "Structurally Valid"
    );

    const unsupported = detectedFragments.filter(
      (fragment) =>
        fragment.integrity_status === "Unsupported Validation"
    );

    const invalid = detectedFragments.filter(
      (fragment) =>
        fragment.integrity_status === "Corrupted or Incomplete" ||
        fragment.integrity_status === "Corrupted"
    );

    const integrityValues = detectedFragments
      .map((fragment) => fragment.structural_integrity)
      .filter(
        (value) =>
          typeof value === "number" && !Number.isNaN(value)
      );

    const averageIntegrity =
      integrityValues.length > 0
        ? integrityValues.reduce(
            (sum, value) => sum + value,
            0
          ) / integrityValues.length
        : null;

    const verifiedBytes = detectedFragments.reduce(
      (total, fragment) =>
        total + Number(fragment.verified_bytes || 0),
      0
    );

    const inferredBytes = detectedFragments.reduce(
      (total, fragment) =>
        total + Number(fragment.inferred_bytes || 0),
      0
    );

    return {
      completed: pending.length === 0,
      validCount: valid.length,
      invalidCount: invalid.length,
      unsupportedCount: unsupported.length,
      pendingCount: pending.length,
      averageIntegrity,
      verifiedBytes,
      inferredBytes,
    };
  }, [detectedFragments]);

  const integrityStatus = useMemo(() => {
    if (!detectedFragments.length) return "No Candidate";

    if (validationSummary.pendingCount > 0) {
      return "Pending Structural Validation";
    }

    if (
      validationSummary.validCount ===
      detectedFragments.length
    ) {
      return "Structurally Valid";
    }

    if (validationSummary.invalidCount > 0) {
      return "Corrupted or Incomplete";
    }

    if (
      validationSummary.unsupportedCount ===
      detectedFragments.length
    ) {
      return "Unsupported Validation";
    }

    return "Validation Completed";
  }, [detectedFragments, validationSummary]);

  const recoveryStatus = useMemo(() => {
    if (!detectedFragments.length) {
      return "No Recovery Candidates Detected";
    }

    if (validationSummary.pendingCount > 0) {
      return "Candidate Evidence Detected";
    }

    if (
      validationSummary.validCount ===
      detectedFragments.length
    ) {
      return "Structurally Valid Candidate";
    }

    if (validationSummary.validCount > 0) {
      return "Partially Validated";
    }

    return "Candidate Evidence Detected";
  }, [detectedFragments, validationSummary]);

  const pipeline = useMemo(() => {
    if (loading) {
      return [
        ["Evidence Scan", "Running", 20],
        ["File Signature Detection", "Pending", 0],
        ["Fragment Detection", "Pending", 0],
        ["Fragment Classification", "Pending", 0],
        ["Structural Validation", "Pending", 0],
        ["Fragment Relationship Analysis", "Pending", 0],
      ];
    }

    const hasEvidence = Boolean(activeEvidence?.evidence_id);
    const hasScan = Boolean(analysis);
    const hasFragments = detectedFragments.length > 0;
    const validationCompleted =
      hasFragments &&
      validationSummary.pendingCount === 0;
    const hasRelationships = relationships.length > 0;

    return [
      [
        "Evidence Scan",
        hasEvidence && hasScan ? "Completed" : hasEvidence ? "Running" : "Pending",
        hasEvidence && hasScan ? 100 : hasEvidence ? 60 : 0,
      ],
      [
        "File Signature Detection",
        hasScan ? "Completed" : "Pending",
        hasScan ? 100 : 0,
      ],
      [
        "Fragment Detection",
        hasScan ? "Completed" : "Pending",
        hasScan ? 100 : 0,
      ],
      [
        "Fragment Classification",
        hasFragments ? "Completed" : "Pending",
        hasFragments ? 100 : 0,
      ],
      [
        "Structural Validation",
        validationCompleted
          ? "Completed"
          : hasFragments
          ? "Running"
          : "Pending",
        validationCompleted
          ? 100
          : hasFragments
          ? 60
          : 0,
      ],
      [
        "Fragment Relationship Analysis",
        hasRelationships ? "Completed" : "Pending",
        hasRelationships ? 100 : 0,
      ],
    ];
  }, [
    loading,
    activeEvidence,
    analysis,
    detectedFragments,
    validationSummary,
    relationships,
  ]);

  const completedStages = pipeline.filter(
    ([, status]) => status === "Completed"
  ).length;

  const activePercent = Math.round(
    (completedStages / pipeline.length) * 100
  );

  const bytesLabel = formatBytes(bytesScanned);
  const verifiedBytesLabel = formatBytes(
    validationSummary.verifiedBytes
  );
  const inferredBytesLabel = formatBytes(
    validationSummary.inferredBytes
  );

  const integrityPercentage =
    validationSummary.averageIntegrity !== null
      ? `${validationSummary.averageIntegrity.toFixed(1)}%`
      : "—";

  const primaryValidationMessage =
    detectedFragments.length > 0
      ? detectedFragments[0].validation_message
      : null;

  if (loading) {
    return (
      <div className="page-intro">
        <div>
          <span className="eyebrow">AI RECOVERY PIPELINE</span>
          <h2>Recovery Analysis</h2>
          <p className="muted">
            Loading live forensic analysis results...
          </p>
        </div>
        <Badge tone="info">LOADING</Badge>
      </div>
    );
  }

  return (
    <div>
      <div className="page-intro">
        <div>
          <span className="eyebrow">AI RECOVERY PIPELINE</span>
          <h2>Recovery Analysis</h2>
          <p className="muted">
            Live evidence scan, fragment classification,
            structural validation and relationship analysis.
          </p>
        </div>

        <Badge tone="info">{activePercent}% ACTIVE</Badge>
      </div>

      {error && (
        <Card>
          <div className="contradiction">
            <AlertTriangle size={18} />
            <div>
              <b>Analysis Error</b>
              <p style={{ whiteSpace: "pre-line" }}>{error}</p>
            </div>
          </div>
        </Card>
      )}

      {message && (
        <Card>
          <div className="contradiction">
            <CheckCircle2 size={18} />
            <div>
              <b>Analysis Update</b>
              <p>{message}</p>
            </div>
          </div>
        </Card>
      )}

      {evidenceItems.length > 0 && (
        <Card>
          <div className="card-title">
            <span>Investigation Evidence</span>
            <Badge tone="info">
              {evidenceItems.length} ITEM
              {evidenceItems.length === 1 ? "" : "S"}
            </Badge>
          </div>

          <div
            style={{
              display: "flex",
              gap: "8px",
              flexWrap: "wrap",
            }}
          >
            {evidenceItems.map((item) => {
              const active =
                item.evidence_id ===
                activeEvidence?.evidence_id;

              return (
                <button
                  key={item.evidence_id}
                  type="button"
                  onClick={() => selectEvidence(item)}
                  style={{
                    border: active
                      ? "1px solid #0284c7"
                      : "1px solid #dbe3ec",
                    background: active
                      ? "#eff6ff"
                      : "#ffffff",
                    color: "#0f172a",
                    borderRadius: "8px",
                    padding: "9px 12px",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <strong
                    style={{
                      display: "block",
                      fontSize: "12px",
                    }}
                  >
                    {item.filename}
                  </strong>
                  <span
                    style={{
                      display: "block",
                      marginTop: "3px",
                      color: "#64748b",
                      fontSize: "10px",
                    }}
                  >
                    {item.evidence_id} ·{" "}
                    {formatBytes(item.size_bytes)}
                  </span>
                </button>
              );
            })}
          </div>
        </Card>
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: "8px",
          marginBottom: "14px",
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          onClick={loadWorkspace}
          disabled={running || relationshipRunning}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "7px",
            border: "1px solid #d7e0ea",
            borderRadius: "8px",
            background: "#fff",
            color: "#334155",
            padding: "9px 13px",
            cursor: "pointer",
          }}
        >
          <RefreshCw size={14} />
          Refresh Analysis
        </button>

        <button
          type="button"
          onClick={runAnalysis}
          disabled={
            running || !activeEvidence?.evidence_id
          }
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "7px",
            border: "1px solid #0284c7",
            borderRadius: "8px",
            background: "#0284c7",
            color: "#fff",
            padding: "9px 13px",
            cursor: "pointer",
            opacity:
              running || !activeEvidence?.evidence_id
                ? 0.55
                : 1,
          }}
        >
          {running ? (
            <LoaderCircle
              size={14}
              className="spin"
            />
          ) : (
            <Play size={14} />
          )}
          {running ? "Running Analysis" : "Run Analysis"}
        </button>

        <button
          type="button"
          onClick={runRelationships}
          disabled={
            relationshipRunning ||
            !investigationId ||
            detectedFragments.length < 2
          }
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "7px",
            border: "1px solid #0ea5e9",
            borderRadius: "8px",
            background: "#fff",
            color: "#0369a1",
            padding: "9px 13px",
            cursor: "pointer",
            opacity:
              relationshipRunning ||
              !investigationId ||
              detectedFragments.length < 2
                ? 0.55
                : 1,
          }}
        >
          {relationshipRunning ? (
            <LoaderCircle
              size={14}
              className="spin"
            />
          ) : (
            <Network size={14} />
          )}
          {relationshipRunning
            ? "Analyzing Relationships"
            : "Analyze Relationships"}
        </button>
      </div>

      <div className="analysis-grid">
        <Card>
          <div className="card-title">
            <span>Pipeline Execution</span>
            <span className="live-label">
              <i />
              LIVE
            </span>
          </div>

          <div className="pipeline">
            {pipeline.map(
              ([name, status, progress]) => (
                <div
                  className="pipeline-row"
                  key={name}
                >
                  <div
                    className={`pipeline-icon ${status.toLowerCase()}`}
                  >
                    {status === "Completed" ? (
                      <CheckCircle2 size={15} />
                    ) : status === "Running" ? (
                      <LoaderCircle
                        className="spin"
                        size={15}
                      />
                    ) : (
                      <Circle size={15} />
                    )}
                  </div>

                  <div className="pipeline-main">
                    <div>
                      <b>{name}</b>
                      <span>{status}</span>
                    </div>
                    <ProgressBar value={progress} />
                  </div>
                </div>
              )
            )}
          </div>
        </Card>

        <div className="side-stack">
          <Card>
            <div className="card-title">
              Recovery Feasibility
            </div>

            <div className="feasibility-score">
              {detectedFragments.length > 0
                ? "—"
                : "0"}
            </div>

            <p className="muted">
              {activeEvidence?.filename ||
                "No evidence selected"}
            </p>

            <div className="metric-line">
              <span>Fragments detected</span>
              <b>{detectedFragments.length}</b>
            </div>

            <div className="metric-line">
              <span>Structural validation</span>
              <b>{integrityPercentage}</b>
            </div>

            <div className="metric-line">
              <span>Metadata</span>
              <b>
                {activeEvidence?.metadata
                  ? "Available"
                  : "Unavailable"}
              </b>
            </div>

            <div className="metric-line">
              <span>Recovery status</span>
              <b>{recoveryStatus}</b>
            </div>

            <Badge
              tone={
                validationSummary.completed &&
                validationSummary.validCount > 0
                  ? "success"
                  : detectedFragments.length > 0
                  ? "info"
                  : "warning"
              }
            >
              {validationSummary.completed &&
              validationSummary.validCount > 0
                ? "VALIDATED"
                : detectedFragments.length > 0
                ? "CANDIDATE DETECTED"
                : "NO CANDIDATE"}
            </Badge>
          </Card>

          <Card>
            <div className="card-title">
              Integrity Assessment
            </div>

            <div className="contradiction">
              {integrityStatus ===
              "Structurally Valid" ? (
                <CheckCircle2 size={17} />
              ) : (
                <AlertTriangle size={17} />
              )}

              <div>
                <b>{integrityStatus}</b>

                {validationSummary.completed ? (
                  <>
                    <div className="metric-line">
                      <span>Structural Integrity</span>
                      <b>{integrityPercentage}</b>
                    </div>

                    <div className="metric-line">
                      <span>Verified Bytes</span>
                      <b>{verifiedBytesLabel}</b>
                    </div>

                    <div className="metric-line">
                      <span>Inferred Bytes</span>
                      <b>{inferredBytesLabel}</b>
                    </div>

                    {validationSummary.invalidCount >
                      0 && (
                      <div className="metric-line">
                        <span>
                          Corrupted / Incomplete
                        </span>
                        <b>
                          {validationSummary.invalidCount}
                        </b>
                      </div>
                    )}

                    {validationSummary.unsupportedCount >
                      0 && (
                      <div className="metric-line">
                        <span>Unsupported</span>
                        <b>
                          {
                            validationSummary.unsupportedCount
                          }
                        </b>
                      </div>
                    )}

                    {primaryValidationMessage && (
                      <p>{primaryValidationMessage}</p>
                    )}
                  </>
                ) : (
                  <p>
                    Signature detection alone does not
                    establish that a complete file has
                    been recovered.
                  </p>
                )}
              </div>
            </div>

            <small className="muted">
              {validationSummary.completed
                ? "Structural validation completed using the recovery backend."
                : "Structural validation is being evaluated from available candidate evidence."}
            </small>
          </Card>
        </div>
      </div>

      <Card>
        <div className="card-title">
          Scan Telemetry
        </div>

        <div className="telemetry">
          <div>
            <small>Bytes scanned</small>
            <b>{bytesLabel}</b>
          </div>

          <div>
            <small>Fragments</small>
            <b>{detectedFragments.length}</b>
          </div>

          <div>
            <small>Candidate files</small>
            <b>{analysis?.files_scanned || 0}</b>
          </div>

          <div>
            <small>Evidence ID</small>
            <b className="mono">
              {activeEvidence?.evidence_id || "—"}
            </b>
          </div>

          <div>
            <small>Signatures</small>
            <b>
              {detectedTypes.length
                ? detectedTypes.join(" · ")
                : "None detected"}
            </b>
          </div>
        </div>
      </Card>

      {detectedFragments.length > 0 && (
        <Card>
          <div className="card-title">
            Validation Summary
          </div>

          <div className="telemetry">
            <div>
              <small>Validated</small>
              <b>{validationSummary.validCount}</b>
            </div>

            <div>
              <small>Corrupted / Incomplete</small>
              <b>{validationSummary.invalidCount}</b>
            </div>

            <div>
              <small>Unsupported</small>
              <b>
                {validationSummary.unsupportedCount}
              </b>
            </div>

            <div>
              <small>Verified Bytes</small>
              <b>{verifiedBytesLabel}</b>
            </div>

            <div>
              <small>Inferred Bytes</small>
              <b>{inferredBytesLabel}</b>
            </div>
          </div>
        </Card>
      )}

      {detectedFragments.length > 0 && (
        <Card>
          <div className="card-title">
            Detected Fragments
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fragment ID</th>
                  <th>Type</th>
                  <th>Offset</th>
                  <th>Sample</th>
                  <th>Entropy</th>
                  <th>Integrity</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {detectedFragments.map((fragment) => (
                  <tr key={fragment.fragment_id}>
                    <td className="mono">
                      {fragment.fragment_id || "—"}
                    </td>

                    <td>
                      {fragment.file_type || "Unknown"}
                    </td>

                    <td>
                      {formatBytes(fragment.offset)}
                    </td>

                    <td>
                      {formatBytes(fragment.sample_size)}
                    </td>

                    <td>
                      {fragment.entropy ?? "—"}
                    </td>

                    <td>
                      {typeof fragment.structural_integrity ===
                      "number"
                        ? `${fragment.structural_integrity}%`
                        : "Pending"}
                    </td>

                    <td>
                      <Badge
                        tone={toneForIntegrity(
                          fragment.integrity_status
                        )}
                      >
                        {fragment.integrity_status ||
                          fragment.recovery_status ||
                          "Candidate"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card>
        <div className="card-title">
          Fragment Relationship Analysis
        </div>

        {relationships.length === 0 ? (
          <div className="contradiction">
            <Network size={17} />
            <div>
              <b>No persisted relationships for this evidence</b>
              <p>
                Run relationship analysis when at least two
                compatible fragment candidates are available.
                A single intact file does not create a
                fabricated relationship.
              </p>
            </div>
          </div>
        ) : (
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
                {relationships.map((relationship) => (
                  <tr
                    key={
                      relationship.relationship_id ||
                      `${relationship.fragment_a_id}-${relationship.fragment_b_id}`
                    }
                  >
                    <td className="mono">
                      {relationship.fragment_a_id}
                    </td>
                    <td className="mono">
                      {relationship.fragment_b_id}
                    </td>
                    <td>
                      {relationship.relationship || "Candidate"}
                    </td>
                    <td>
                      {typeof relationship.relationship_score ===
                      "number"
                        ? `${(
                            relationship.relationship_score *
                            100
                          ).toFixed(1)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {!activeEvidence && (
        <Card>
          <div className="card-title">
            No Live Evidence Loaded
          </div>
          <p className="muted">
            Start a new investigation and upload evidence
            to populate this page with real backend results.
          </p>
        </Card>
      )}

      <style>{`
        .spin {
          animation: recoverai-spin 0.9s linear infinite;
        }

        @keyframes recoverai-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

