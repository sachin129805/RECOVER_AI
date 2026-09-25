import React, { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Circle,
  LoaderCircle,
  AlertTriangle,
} from "lucide-react";

import Card from "../components/common/Card";
import ProgressBar from "../components/common/ProgressBar";
import Badge from "../components/common/Badge";

const API_URL = "http://127.0.0.1:8000";

export default function RecoveryAnalysis() {
  const [evidence, setEvidence] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedEvidence = localStorage.getItem(
      "recoverai_current_evidence"
    );

    const storedAnalysis = localStorage.getItem(
      "recoverai_analysis_result"
    );

    if (storedEvidence) {
      setEvidence(JSON.parse(storedEvidence));
    }

    if (storedAnalysis) {
      setAnalysis(JSON.parse(storedAnalysis));
    }

    setLoading(false);
  }, []);

  /*
   * Flatten all detected fragments from the backend response.
   */
  const fragments = useMemo(() => {
    if (!analysis?.results) return [];

    return analysis.results.flatMap(
      (result) => result.detections || []
    );
  }, [analysis]);

  /*
   * Unique detected file types.
   */
  const detectedTypes = useMemo(() => {
    return [
      ...new Set(
        fragments
          .map((fragment) => fragment.file_type)
          .filter(Boolean)
      ),
    ];
  }, [fragments]);

  /*
   * Calculate bytes scanned from actual backend results.
   */
  const bytesScanned = useMemo(() => {
    if (!analysis?.results) return 0;

    return analysis.results.reduce(
      (total, result) => total + (result.size_bytes || 0),
      0
    );
  }, [analysis]);

  /*
   * Structural validation summary.
   */
  const validationSummary = useMemo(() => {
    if (!fragments.length) {
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

    const pending = fragments.filter(
      (fragment) =>
        fragment.structural_integrity === null ||
        fragment.structural_integrity === undefined
    );

    const valid = fragments.filter(
      (fragment) =>
        fragment.integrity_status === "Structurally Valid"
    );

    const unsupported = fragments.filter(
      (fragment) =>
        fragment.integrity_status === "Unsupported Validation"
    );

    const invalid = fragments.filter(
      (fragment) =>
        fragment.integrity_status === "Corrupted or Incomplete" ||
        fragment.integrity_status === "Corrupted"
    );

    const integrityValues = fragments
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

    const verifiedBytes = fragments.reduce(
      (total, fragment) =>
        total + (fragment.verified_bytes || 0),
      0
    );

    const inferredBytes = fragments.reduce(
      (total, fragment) =>
        total + (fragment.inferred_bytes || 0),
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
  }, [fragments]);

  /*
   * Human-readable aggregate integrity status.
   */
  const integrityStatus = useMemo(() => {
    if (!fragments.length) {
      return "No Candidate";
    }

    if (validationSummary.pendingCount > 0) {
      return "Pending Structural Validation";
    }

    if (
      validationSummary.validCount === fragments.length
    ) {
      return "Structurally Valid";
    }

    if (validationSummary.invalidCount > 0) {
      return "Corrupted or Incomplete";
    }

    if (
      validationSummary.unsupportedCount === fragments.length
    ) {
      return "Unsupported Validation";
    }

    return "Validation Completed";
  }, [fragments, validationSummary]);

  /*
   * Recovery status.
   */
  const recoveryStatus = useMemo(() => {
    if (!fragments.length) {
      return "No Recovery Candidates Detected";
    }

    if (validationSummary.pendingCount > 0) {
      return "Candidate Evidence Detected";
    }

    if (validationSummary.validCount === fragments.length) {
      return "Structurally Valid Candidate";
    }

    if (validationSummary.validCount > 0) {
      return "Partially Validated";
    }

    return "Candidate Evidence Detected";
  }, [fragments, validationSummary]);

  /*
   * Validation message for the primary fragment.
   */
  const primaryValidationMessage =
    fragments.length > 0
      ? fragments[0].validation_message
      : null;

  /*
   * Build the pipeline from real backend state.
   */
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

    const hasEvidence = Boolean(evidence?.evidence_id);
    const hasScan = Boolean(analysis);
    const hasFragments = fragments.length > 0;

    const validationCompleted =
      hasFragments &&
      validationSummary.pendingCount === 0;

    return [
      [
        "Evidence Scan",
        hasEvidence ? "Completed" : "Pending",
        hasEvidence ? 100 : 0,
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
        "Pending",
        0,
      ],
    ];
  }, [
    loading,
    evidence,
    analysis,
    fragments,
    validationSummary,
  ]);

  const completedStages = pipeline.filter(
    ([, status]) => status === "Completed"
  ).length;

  const activePercent = Math.round(
    (completedStages / pipeline.length) * 100
  );

  const bytesLabel =
    bytesScanned >= 1024 * 1024
      ? `${(bytesScanned / (1024 * 1024)).toFixed(2)} MB`
      : `${bytesScanned} bytes`;

  const verifiedBytesLabel =
    validationSummary.verifiedBytes >= 1024 * 1024
      ? `${(
          validationSummary.verifiedBytes /
          (1024 * 1024)
        ).toFixed(2)} MB`
      : `${validationSummary.verifiedBytes} bytes`;

  const inferredBytesLabel =
    validationSummary.inferredBytes >= 1024 * 1024
      ? `${(
          validationSummary.inferredBytes /
          (1024 * 1024)
        ).toFixed(2)} MB`
      : `${validationSummary.inferredBytes} bytes`;

  const integrityPercentage =
    validationSummary.averageIntegrity !== null
      ? `${validationSummary.averageIntegrity.toFixed(1)}%`
      : "—";

  if (loading) {
    return (
      <div className="page-intro">
        <div>
          <span className="eyebrow">
            AI RECOVERY PIPELINE
          </span>

          <h2>Recovery Analysis</h2>

          <p className="muted">
            Loading forensic analysis results...
          </p>
        </div>

        <Badge tone="info">LOADING</Badge>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="page-intro">
        <div>
          <span className="eyebrow">
            AI RECOVERY PIPELINE
          </span>

          <h2>Recovery Analysis</h2>

          <p className="muted">
            Live analysis results from the RECOVERAI
            forensic backend.
          </p>
        </div>

        <Badge tone="info">
          {activePercent}% ACTIVE
        </Badge>
      </div>

      <div className="analysis-grid">

        {/* Pipeline */}
        <Card>
          <div className="card-title">
            <span>Pipeline Execution</span>

            <span className="live-label">
              <i />
              LIVE
            </span>
          </div>

          <div className="pipeline">
            {pipeline.map(([name, status, progress]) => (
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
            ))}
          </div>
        </Card>

        {/* Recovery / Integrity */}
        <div className="side-stack">

          {/* Recovery Feasibility */}
          <Card>
            <div className="card-title">
              Recovery Feasibility
            </div>

            <div className="feasibility-score">
              {fragments.length > 0 ? "—" : "0"}
            </div>

            <p className="muted">
              {evidence?.filename ||
                "No evidence selected"}
            </p>

            <div className="metric-line">
              <span>Fragments detected</span>
              <b>{fragments.length}</b>
            </div>

            <div className="metric-line">
              <span>Structural validation</span>
              <b>{integrityPercentage}</b>
            </div>

            <div className="metric-line">
              <span>Metadata</span>
              <b>
                {evidence?.metadata
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
                  : fragments.length > 0
                  ? "info"
                  : "warning"
              }
            >
              {validationSummary.completed &&
              validationSummary.validCount > 0
                ? "VALIDATED"
                : fragments.length > 0
                ? "CANDIDATE DETECTED"
                : "NO CANDIDATE"}
            </Badge>
          </Card>

          {/* Integrity */}
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
                        <span>Corrupted / Incomplete</span>
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
                      <p>
                        {primaryValidationMessage}
                      </p>
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
                ? "Structural validation completed using the recovered candidate bytes."
                : "Structural validation is being evaluated by the recovery backend."}
            </small>
          </Card>

        </div>
      </div>

      {/* Real scan telemetry */}
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
            <b>{fragments.length}</b>
          </div>

          <div>
            <small>Candidate files</small>
            <b>
              {analysis?.files_scanned || 0}
            </b>
          </div>

          <div>
            <small>Evidence ID</small>
            <b className="mono">
              {evidence?.evidence_id || "—"}
            </b>
          </div>

          <div>
            <small>Signatures</small>

            <b>
              {detectedTypes.length > 0
                ? detectedTypes.join(" · ")
                : "None detected"}
            </b>
          </div>

        </div>
      </Card>

      {/* Validation Summary */}
      {fragments.length > 0 && (
        <Card>
          <div className="card-title">
            Validation Summary
          </div>

          <div className="telemetry">

            <div>
              <small>Validated</small>
              <b>
                {validationSummary.validCount}
              </b>
            </div>

            <div>
              <small>Corrupted / Incomplete</small>
              <b>
                {validationSummary.invalidCount}
              </b>
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

      {/* Fragment details */}
      {fragments.length > 0 && (
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
                {fragments.map((fragment) => (
                  <tr key={fragment.fragment_id}>

                    <td className="mono">
                      {fragment.fragment_id}
                    </td>

                    <td>
                      {fragment.file_type}
                    </td>

                    <td>
                      {fragment.offset} bytes
                    </td>

                    <td>
                      {fragment.sample_size} bytes
                    </td>

                    <td>
                      {fragment.entropy}
                    </td>

                    <td>
                      {typeof fragment.structural_integrity ===
                      "number"
                        ? `${fragment.structural_integrity}%`
                        : "Pending"}
                    </td>

                    <td>
                      <Badge
                        tone={
                          fragment.integrity_status ===
                          "Structurally Valid"
                            ? "success"
                            : fragment.integrity_status ===
                              "Corrupted or Incomplete"
                            ? "warning"
                            : "info"
                        }
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

      {/* No evidence state */}
      {!evidence && (
        <Card>
          <div className="card-title">
            No Live Evidence Loaded
          </div>

          <p className="muted">
            Start a new investigation and upload evidence
            to populate this analysis with real backend
            results.
          </p>
        </Card>
      )}
    </div>
  );
}