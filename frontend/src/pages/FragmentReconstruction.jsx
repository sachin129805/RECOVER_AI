import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  MousePointer2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { Canvas } from "@react-three/fiber";
import {
  OrbitControls,
  Float,
  Line,
  Text,
} from "@react-three/drei";

import Card from "../components/common/Card";
import Badge from "../components/common/Badge";
import {
  getInvestigationFragments,
  getInvestigationRelationships,
  getInvestigationEvidence,
  runReconstruction,
  getReconstructionResults,
  getReconstructionAssessment,
  getReconstructionContributions,
  getReconstructionPriority,
  getReconstructionDna,
  getReconstructionProvenance,
} from "../api";


function formatBytes(value) {
  const bytes = Number(value || 0);

  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(2)} KB`;
  }

  return `${bytes} B`;
}


function formatPercent(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }

  const number = Number(value);

  if (Number.isNaN(number)) {
    return "N/A";
  }

  return `${Math.round(number <= 1 ? number * 100 : number)}%`;
}


function getFragmentStatus(fragment) {
  const status =
    fragment.recovery_status ||
    fragment.integrity_status ||
    "";

  if (status.includes("Verified")) {
    return "Verified";
  }

  if (status.includes("Inferred")) {
    return "Inferred";
  }

  if (
    status.includes("Corrupted") ||
    status.includes("Unable")
  ) {
    return "Unrecoverable";
  }

  return "Structural";
}


function getStatusTone(status) {
  if (status === "Verified") return "success";
  if (status === "Inferred") return "warning";
  if (status === "Unrecoverable") return "danger";
  return "info";
}


/*
 * 3D fragment node
 */
function FragmentNode({
  position,
  label,
  selected,
  status,
  onClick,
}) {
  const verified = status === "Verified";
  const inferred = status === "Inferred";

  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      <Float
        speed={1.2}
        rotationIntensity={0.15}
        floatIntensity={0.2}
      >
        <mesh>
          <sphereGeometry
            args={[
              selected ? 0.24 : 0.18,
              20,
              20,
            ]}
          />

          <meshStandardMaterial
            color={
              selected
                ? "#0ea5e9"
                : verified
                ? "#16a34a"
                : inferred
                ? "#d97706"
                : "#475569"
            }
            emissive={
              selected
                ? "#38bdf8"
                : verified
                ? "#22c55e"
                : inferred
                ? "#f59e0b"
                : "#64748b"
            }
            emissiveIntensity={
              selected ? 2.5 : 1.1
            }
          />
        </mesh>
      </Float>

      <Text
        position={[0, 0.32, 0]}
        fontSize={0.10}
        color="#cbd5e1"
        anchorX="center"
        anchorY="middle"
      >
        {label}
      </Text>
    </group>
  );
}


/*
 * Dynamic 3D relationship graph.
 *
 * Important:
 * This graph uses actual backend fragment IDs and
 * actual relationship IDs. Nothing is generated from
 * demoData.js.
 */
function Graph3D({
  fragments,
  relationships,
  selectedId,
  setSelectedId,
}) {
  const positions = useMemo(() => {
    const count = fragments.length;

    if (!count) {
      return {};
    }

    const radius = count <= 3 ? 1.8 : 2.4;

    const result = {};

    fragments.forEach((fragment, index) => {
      const angle =
        (index / Math.max(count, 1)) *
        Math.PI *
        2;

      result[fragment.fragment_id] = [
        Math.cos(angle) * radius,
        Math.sin(angle) * 1.45,
        Math.sin(index * 1.7) * 0.7,
      ];
    });

    return result;
  }, [fragments]);


  const graphRelationships = useMemo(() => {
    return relationships.filter((relationship) => {
      const a =
        relationship.fragment_a_id;

      const b =
        relationship.fragment_b_id;

      return (
        positions[a] &&
        positions[b]
      );
    });
  }, [relationships, positions]);


  if (!fragments.length) {
    return (
      <div
        style={{
          height: "420px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          color: "#64748b",
          padding: "40px",
        }}
      >
        <div>
          <AlertTriangle
            size={32}
            style={{ marginBottom: 12 }}
          />

          <div
            style={{
              fontWeight: 600,
              color: "#334155",
            }}
          >
            No fragments available
          </div>

          <div
            style={{
              marginTop: 6,
              fontSize: 13,
            }}
          >
            Analyze the investigation first.
          </div>
        </div>
      </div>
    );
  }


  return (
    <div className="graph-3d">
      <Canvas
        camera={{
          position: [0, 0, 6],
          fov: 48,
        }}
      >
        <ambientLight intensity={0.7} />

        <pointLight
          position={[3, 3, 4]}
          intensity={18}
          color="#38bdf8"
        />

        <pointLight
          position={[-3, -2, 2]}
          intensity={8}
          color="#22c55e"
        />

        <gridHelper
          args={[
            12,
            12,
            "#1e293b",
            "#0f172a",
          ]}
        />

        {graphRelationships.map(
          (relationship) => {
            const start =
              positions[
                relationship.fragment_a_id
              ];

            const end =
              positions[
                relationship.fragment_b_id
              ];

            const score = Number(
              relationship.relationship_score || 0
            );

            return (
              <Line
                key={
                  relationship.relationship_id
                }
                points={[start, end]}
                color={
                  score >= 0.85
                    ? "#38bdf8"
                    : "#475569"
                }
                lineWidth={
                  score >= 0.85 ? 2 : 1
                }
              />
            );
          }
        )}


        {fragments.map(
          (fragment) => {
            const position =
              positions[
                fragment.fragment_id
              ];

            return (
              <FragmentNode
                key={fragment.fragment_id}
                position={position}
                label={fragment.fragment_id}
                selected={
                  selectedId ===
                  fragment.fragment_id
                }
                status={getFragmentStatus(
                  fragment
                )}
                onClick={() =>
                  setSelectedId(
                    fragment.fragment_id
                  )
                }
              />
            );
          }
        )}

        <OrbitControls
          enablePan={false}
        />
      </Canvas>

      <div className="graph-overlay">
        <MousePointer2 size={14} />
        Drag to orbit · Scroll to zoom ·
        Click a fragment
      </div>
    </div>
  );
}


export default function FragmentReconstruction() {
  const [fragments, setFragments] = useState([]);
  const [relationships, setRelationships] =
    useState([]);

  const [selectedId, setSelectedId] =
    useState(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const [investigationEvidence, setInvestigationEvidence] =
    useState([]);

  const [reconstructionResults, setReconstructionResults] =
    useState([]);

  const [reconstructionAssessments, setReconstructionAssessments] =
    useState({});

  const [reconstructionContributions, setReconstructionContributions] =
    useState({});

  const [reconstructionPriorities, setReconstructionPriorities] =
    useState({});

  const [reconstructionDna, setReconstructionDna] =
    useState({});

  const [reconstructionProvenance, setReconstructionProvenance] =
    useState({});

  const [reconstructionRunning, setReconstructionRunning] =
    useState(false);

  const [reconstructionMessage, setReconstructionMessage] =
    useState("");

  const [reconstructionError, setReconstructionError] =
    useState("");


  /*
   * Investigation ID comes from the current
   * investigation created by New Investigation.
   */
  const investigationId =
    localStorage.getItem(
      "recoverai_investigation_id"
    );


  const loadData = async () => {
    if (!investigationId) {
      setError(
        "No active investigation found."
      );

      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");
    setReconstructionError("");

    try {
      const [
        evidenceResponse,
        fragmentResponse,
        relationshipResponse,
      ] = await Promise.all([
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

      const loadedEvidence =
        Array.isArray(evidenceResponse)
          ? evidenceResponse
          : evidenceResponse?.evidence || [];

      const loadedFragments =
        Array.isArray(fragmentResponse)
          ? fragmentResponse
          : fragmentResponse?.fragments || [];

      const loadedRelationships =
        Array.isArray(relationshipResponse)
          ? relationshipResponse
          : relationshipResponse?.relationships || [];

      setInvestigationEvidence(
        loadedEvidence
      );

      setFragments(loadedFragments);
      setRelationships(loadedRelationships);

      if (
        loadedFragments.length &&
        !selectedId
      ) {
        setSelectedId(
          loadedFragments[0].fragment_id
        );
      }

      if (
        selectedId &&
        !loadedFragments.some(
          (fragment) =>
            fragment.fragment_id === selectedId
        )
      ) {
        setSelectedId(
          loadedFragments[0]?.fragment_id || null
        );
      }

      const existingResults = [];

      for (const evidence of loadedEvidence) {
        try {
          const response =
            await getReconstructionResults(
              evidence.evidence_id
            );

          const items =
            Array.isArray(response)
              ? response
              : response?.results || [];

          existingResults.push(
            ...items.map((item) => ({
              ...item,
              evidence_id:
                item.evidence_id ||
                evidence.evidence_id,
              filename:
                item.filename ||
                evidence.filename,
            }))
          );
        } catch (resultError) {
          console.warn(
            `Unable to load reconstruction results for ${evidence.evidence_id}:`,
            resultError
          );
        }
      }

      setReconstructionResults(
        existingResults
      );

    } catch (err) {
      console.error(
        "Failed to load fragment intelligence:",
        err
      );

      setError(
        err.message ||
          "Unable to load fragment analysis."
      );
    } finally {
      setLoading(false);
    }
  };


  const handleRunReconstruction = async () => {
    if (!investigationEvidence.length) {
      setReconstructionError(
        "No evidence artifacts are attached to the active investigation."
      );
      return;
    }

    setReconstructionRunning(true);
    setReconstructionError("");
    setReconstructionMessage("");

    try {
      const generatedResults = [];

      for (const evidence of investigationEvidence) {
        try {
          const result =
            await runReconstruction(
              evidence.evidence_id
            );

          generatedResults.push({
            ...result,
            evidence_id:
              evidence.evidence_id,
            filename: evidence.filename,
          });
        } catch (err) {
          generatedResults.push({
            evidence_id:
              evidence.evidence_id,
            filename: evidence.filename,
            status: "Unable to Recover",
            message:
              err.message ||
              "Reconstruction failed.",
          });
        }
      }

      setReconstructionResults(
        generatedResults
      );

      const assessments = {};
      const contributions = {};
      const priorities = {};
      const dna = {};
      const provenance = {};

      for (const result of generatedResults) {
        if (!result.reconstruction_id) {
          continue;
        }

        const id =
          result.reconstruction_id;

        try {
          assessments[id] =
            await getReconstructionAssessment(id);
        } catch (err) {
          console.warn(
            "Assessment unavailable:",
            err
          );
        }

        try {
          contributions[id] =
            await getReconstructionContributions(id);
        } catch (err) {
          console.warn(
            "Contribution analysis unavailable:",
            err
          );
        }

        try {
          priorities[id] =
            await getReconstructionPriority(id);
        } catch (err) {
          console.warn(
            "Priority analysis unavailable:",
            err
          );
        }

        try {
          dna[id] =
            await getReconstructionDna(id);
        } catch (err) {
          console.warn(
            "Evidence DNA unavailable:",
            err
          );
        }

        try {
          provenance[id] =
            await getReconstructionProvenance(id);
        } catch (err) {
          console.warn(
            "Provenance unavailable:",
            err
          );
        }
      }

      setReconstructionAssessments(
        assessments
      );
      setReconstructionContributions(
        contributions
      );
      setReconstructionPriorities(
        priorities
      );
      setReconstructionDna(dna);
      setReconstructionProvenance(
        provenance
      );

      setReconstructionMessage(
        "Reconstruction analysis completed. Results are derived from the current investigation evidence."
      );
    } catch (err) {
      console.error(
        "Reconstruction failed:",
        err
      );

      setReconstructionError(
        err.message ||
          "Unable to run reconstruction."
      );
    } finally {
      setReconstructionRunning(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [investigationId]);


  const selectedFragment =
    fragments.find(
      (fragment) =>
        fragment.fragment_id ===
        selectedId
    ) || null;


  const selectedRelationships =
    useMemo(() => {
      if (!selectedFragment) {
        return [];
      }

      return relationships.filter(
        (relationship) =>
          relationship.fragment_a_id ===
            selectedFragment.fragment_id ||
          relationship.fragment_b_id ===
            selectedFragment.fragment_id
      );
    }, [
      relationships,
      selectedFragment,
    ]);


  const relationshipAverage =
    useMemo(() => {
      if (!relationships.length) {
        return null;
      }

      const scores =
        relationships
          .map((relationship) =>
            Number(
              relationship.relationship_score
            )
          )
          .filter(
            (score) =>
              !Number.isNaN(score)
          );

      if (!scores.length) {
        return null;
      }

      return (
        scores.reduce(
          (sum, score) =>
            sum + score,
          0
        ) / scores.length
      );
    }, [relationships]);


  const statusCounts =
    useMemo(() => {
      return fragments.reduce(
        (acc, fragment) => {
          const status =
            getFragmentStatus(
              fragment
            );

          acc[status] =
            (acc[status] || 0) + 1;

          return acc;
        },
        {}
      );
    }, [fragments]);


  const reconstructionSummary =
    useMemo(() => {
      const results =
        reconstructionResults || [];

      return {
        total: results.length,
        verified: results.filter(
          (result) =>
            (result.status || result.recovery_status) ===
            "Verified Recovery"
        ).length,
        structural: results.filter(
          (result) =>
            (result.status || result.recovery_status) ===
            "Structural Repair"
        ).length,
        inferred: results.filter(
          (result) =>
            (result.status || result.recovery_status) ===
            "Inferred Reconstruction"
        ).length,
        unable: results.filter(
          (result) =>
            (result.status || result.recovery_status) ===
            "Unable to Recover"
        ).length,
        verifiedBytes: results.reduce(
          (sum, result) =>
            sum + Number(result.verified_bytes || 0),
          0
        ),
        inferredBytes: results.reduce(
          (sum, result) =>
            sum + Number(result.inferred_bytes || 0),
          0
        ),
        missingBytes: results.reduce(
          (sum, result) =>
            sum + Number(result.missing_bytes || 0),
          0
        ),
      };
    }, [reconstructionResults]);


  /*
   * Contribution is calculated from actual
   * fragment sample sizes, not hardcoded percentages.
   */
  const contributionData =
    useMemo(() => {
      const total =
        fragments.reduce(
          (sum, fragment) =>
            sum +
            Number(
              fragment.sample_size || 0
            ),
          0
        );

      if (!total) {
        return fragments.map(
          (fragment) => ({
            ...fragment,
            contribution: 0,
          })
        );
      }

      return fragments.map(
        (fragment) => ({
          ...fragment,
          contribution:
            (Number(
              fragment.sample_size || 0
            ) /
              total) *
            100,
        })
      );
    }, [fragments]);


  if (loading) {
    return (
      <div className="page-intro">
        <div>
          <span className="eyebrow">
            FRAGMENT INTELLIGENCE
          </span>

          <h2>
            Fragment Reconstruction
          </h2>

          <p>
            Loading investigation
            fragment intelligence...
          </p>
        </div>
      </div>
    );
  }


  return (
    <div>
      <div className="page-intro">
        <div>
          <span className="eyebrow">
            FRAGMENT INTELLIGENCE
          </span>

          <h2>
            Fragment Reconstruction
          </h2>

          <p>
            Dynamic relationship model based
            on signatures, offsets, entropy
            and structural compatibility.
          </p>
        </div>

        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
          }}
        >
          <Badge tone="info">
            {fragments.length} FRAGMENTS
          </Badge>

          <Badge tone="info">
            {relationships.length} RELATIONSHIPS
          </Badge>

          <button
            type="button"
            onClick={loadData}
            title="Refresh fragment analysis"
            style={{
              border: "1px solid #cbd5e1",
              background: "#fff",
              borderRadius: 8,
              padding: "7px 9px",
              cursor: "pointer",
            }}
          >
            <RefreshCw size={15} />
          </button>

          <button
            type="button"
            onClick={handleRunReconstruction}
            disabled={
              reconstructionRunning ||
              !investigationEvidence.length
            }
            style={{
              border: "1px solid #0284c7",
              background: reconstructionRunning
                ? "#e0f2fe"
                : "#0284c7",
              color: reconstructionRunning
                ? "#0369a1"
                : "#ffffff",
              borderRadius: 8,
              padding: "7px 12px",
              cursor: reconstructionRunning
                ? "wait"
                : "pointer",
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            {reconstructionRunning ? (
              <>
                <LoaderCircle
                  size={14}
                  style={{
                    verticalAlign: "-2px",
                    marginRight: 5,
                    animation:
                      "spin 0.9s linear infinite",
                  }}
                />
                RECONSTRUCTING...
              </>
            ) : (
              "RUN RECONSTRUCTION"
            )}
          </button>
        </div>
      </div>


      {error && (
        <Card>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              color: "#b91c1c",
            }}
          >
            <AlertTriangle size={18} />
            {error}
          </div>
        </Card>
      )}


      <div className="recon-grid">
        <Card className="graph-card">
          <div className="card-title">
            <span>
              3D Fragment Relationship Graph
            </span>

            <span className="live-label">
              <i /> LIVE INVESTIGATION DATA
            </span>
          </div>

          <Graph3D
            fragments={fragments}
            relationships={relationships}
            selectedId={selectedId}
            setSelectedId={setSelectedId}
          />
        </Card>


        <div className="side-stack">
          <Card>
            <div className="card-title">
              Selected Fragment
            </div>

            {!selectedFragment ? (
              <div className="muted">
                Select a fragment from the
                graph.
              </div>
            ) : (
              <>
                <div className="fragment-id">
                  {selectedFragment.fragment_id}
                </div>

                <div className="metric-line">
                  <span>Evidence</span>
                  <b>
                    {selectedFragment.evidence_id ||
                      "N/A"}
                  </b>
                </div>

                <div className="metric-line">
                  <span>File</span>
                  <b>
                    {selectedFragment.filename ||
                      "N/A"}
                  </b>
                </div>

                <div className="metric-line">
                  <span>Probable type</span>
                  <b>
                    {selectedFragment.file_type ||
                      "Unknown"}
                  </b>
                </div>

                <div className="metric-line">
                  <span>Offset</span>
                  <b>
                    {Number(
                      selectedFragment.offset ||
                        0
                    ).toLocaleString()}
                  </b>
                </div>

                <div className="metric-line">
                  <span>Sample size</span>
                  <b>
                    {formatBytes(
                      selectedFragment.sample_size
                    )}
                  </b>
                </div>

                <div className="metric-line">
                  <span>Entropy</span>
                  <b>
                    {selectedFragment.entropy ??
                      "N/A"}
                  </b>
                </div>

                <div className="metric-line">
                  <span>Classification confidence</span>
                  <b>
                    {formatPercent(
                      selectedFragment.classification_confidence
                    )}
                  </b>
                </div>

                <div
                  style={{
                    marginTop: 12,
                  }}
                >
                  <Badge
                    tone={getStatusTone(
                      getFragmentStatus(
                        selectedFragment
                      )
                    )}
                  >
                    {getFragmentStatus(
                      selectedFragment
                    ).toUpperCase()}
                  </Badge>
                </div>
              </>
            )}
          </Card>


          <Card>
            <div className="card-title">
              Investigation Summary
            </div>

            <div className="metric-line">
              <span>Total fragments</span>
              <b>{fragments.length}</b>
            </div>

            <div className="metric-line">
              <span>Relationships</span>
              <b>
                {relationships.length}
              </b>
            </div>

            <div className="metric-line">
              <span>Verified</span>
              <b>
                {statusCounts.Verified || 0}
              </b>
            </div>

            <div className="metric-line">
              <span>Structural</span>
              <b>
                {statusCounts.Structural || 0}
              </b>
            </div>

            <div className="metric-line">
              <span>Inferred</span>
              <b>
                {statusCounts.Inferred || 0}
              </b>
            </div>

            <div className="metric-line">
              <span>Relationship average</span>
              <b>
                {relationshipAverage === null
                  ? "N/A"
                  : formatPercent(
                      relationshipAverage
                    )}
              </b>
            </div>
          </Card>
        </div>
      </div>


      <Card>
        <div className="card-title">
          <span>
            Reconstruction Assessment
          </span>

          <span className="muted">
            Backend-derived recovery results
          </span>
        </div>

        {reconstructionError && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              color: "#b91c1c",
              marginBottom: 14,
              fontSize: 12,
            }}
          >
            <AlertTriangle size={16} />
            {reconstructionError}
          </div>
        )}

        {reconstructionMessage && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              color: "#047857",
              marginBottom: 14,
              fontSize: 12,
            }}
          >
            <CheckCircle2 size={16} />
            {reconstructionMessage}
          </div>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(4, minmax(0, 1fr))",
            gap: 10,
            marginBottom: 16,
          }}
        >
          {[
            ["Verified", reconstructionSummary.verified],
            ["Structural", reconstructionSummary.structural],
            ["Inferred", reconstructionSummary.inferred],
            ["Unable", reconstructionSummary.unable],
          ].map(([label, value]) => (
            <div
              key={label}
              style={{
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                padding: "10px 12px",
                background: "#f8fafc",
              }}
            >
              <span
                style={{
                  display: "block",
                  color: "#64748b",
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                {label}
              </span>
              <b
                style={{
                  display: "block",
                  marginTop: 4,
                  fontSize: 16,
                  color: "#0f172a",
                }}
              >
                {value}
              </b>
            </div>
          ))}
        </div>

        {!reconstructionResults.length ? (
          <div
            style={{
              padding: "20px 10px",
              textAlign: "center",
              color: "#64748b",
              fontSize: 12,
            }}
          >
            <ShieldCheck
              size={26}
              style={{ marginBottom: 8 }}
            />
            <div
              style={{
                fontWeight: 600,
                color: "#334155",
              }}
            >
              No reconstruction candidate available yet.
            </div>
            <div style={{ marginTop: 5 }}>
              Run reconstruction after the investigation has been analyzed.
            </div>
          </div>
        ) : (
          <div>
            {reconstructionResults.map(
              (result, index) => {
                const status =
                  result.status ||
                  result.recovery_status ||
                  "Unknown";

                const id =
                  result.reconstruction_id;

                const assessment = id
                  ? reconstructionAssessments[id]
                  : null;

                const confidence =
                  result.recovery_confidence ??
                  assessment?.recovery_confidence;

                return (
                  <div
                    key={
                      id ||
                      `${result.evidence_id}-${index}`
                    }
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: 9,
                      padding: 14,
                      marginTop: index ? 10 : 0,
                      background: "#f8fafc",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 12,
                        marginBottom: 10,
                      }}
                    >
                      <div>
                        <strong
                          style={{
                            display: "block",
                            fontSize: 12,
                            color: "#0f172a",
                          }}
                        >
                          {result.filename ||
                            result.evidence_id ||
                            "Evidence artifact"}
                        </strong>
                        <span
                          style={{
                            fontFamily: "monospace",
                            fontSize: 10,
                            color: "#64748b",
                          }}
                        >
                          {result.evidence_id || "—"}
                        </span>
                      </div>

                      <Badge
                        tone={statusTone(status)}
                      >
                        {status}
                      </Badge>
                    </div>

                    <div className="metric-line">
                      <span>Fragments used</span>
                      <b>
                        {Array.isArray(result.fragments_used)
                          ? result.fragments_used.length
                          : result.fragment_count ?? "—"}
                      </b>
                    </div>

                    <div className="metric-line">
                      <span>Verified bytes</span>
                      <b>
                        {formatBytes(result.verified_bytes)}
                      </b>
                    </div>

                    <div className="metric-line">
                      <span>Inferred bytes</span>
                      <b>
                        {formatBytes(result.inferred_bytes)}
                      </b>
                    </div>

                    <div className="metric-line">
                      <span>Missing bytes</span>
                      <b>
                        {formatBytes(result.missing_bytes)}
                      </b>
                    </div>

                    <div className="metric-line">
                      <span>Recovery confidence</span>
                      <b>
                        {formatPercent(confidence)}
                      </b>
                    </div>

                    {status ===
                      "Inferred Reconstruction" && (
                      <div
                        style={{
                          marginTop: 12,
                          padding: "9px 11px",
                          borderRadius: 7,
                          background: "#fffbeb",
                          border: "1px solid #fde68a",
                          color: "#92400e",
                          fontSize: 11,
                          fontWeight: 700,
                        }}
                      >
                        INFERRED — NOT VERIFIED ORIGINAL DATA
                      </div>
                    )}

                    {result.message && (
                      <div
                        style={{
                          marginTop: 10,
                          color: "#64748b",
                          fontSize: 11,
                        }}
                      >
                        {result.message}
                      </div>
                    )}
                  </div>
                );
              }
            )}
          </div>
        )}
      </Card>


      <Card>
        <div className="card-title">
          <span>
            Fragment Contribution
          </span>

          <span className="muted">
            Based on actual fragment sample
            sizes
          </span>
        </div>

        {!contributionData.length ? (
          <div className="muted">
            No fragment contribution data
            available.
          </div>
        ) : (
          <div className="contribution">
            <div className="contribution-track">
              {contributionData.map(
                (fragment) => (
                  <div
                    key={
                      fragment.fragment_id
                    }
                    style={{
                      width: `${Math.max(
                        fragment.contribution,
                        1
                      )}%`,
                    }}
                    title={
                      fragment.fragment_id
                    }
                  >
                    {fragment.fragment_id}
                  </div>
                )
              )}
            </div>

            <div className="contribution-legend">
              {contributionData
                .slice(0, 12)
                .map((fragment) => (
                  <span
                    key={
                      fragment.fragment_id
                    }
                  >
                    <i className="swatch s0" />

                    {fragment.fragment_id}
                    {" · "}
                    {fragment.contribution.toFixed(
                      1
                    )}
                    %
                  </span>
                ))}
            </div>
          </div>
        )}
      </Card>


      <Card>
        <div className="card-title">
          <span>
            Selected Fragment Relationships
          </span>

          <span className="muted">
            Evidence-backed candidates
          </span>
        </div>

        {!selectedFragment ? (
          <div className="muted">
            Select a fragment to inspect its
            relationships.
          </div>
        ) : !selectedRelationships.length ? (
          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              color: "#64748b",
            }}
          >
            <ShieldCheck size={18} />

            No relationship candidates were
            established for this fragment.
          </div>
        ) : (
          <div>
            {selectedRelationships.map(
              (relationship) => {
                const otherId =
                  relationship.fragment_a_id ===
                  selectedFragment.fragment_id
                    ? relationship.fragment_b_id
                    : relationship.fragment_a_id;

                return (
                  <div
                    key={
                      relationship.relationship_id
                    }
                    className="metric-line"
                  >
                    <span>
                      {otherId}
                    </span>

                    <b>
                      {formatPercent(
                        relationship.relationship_score
                      )}

                      {" · "}

                      {relationship.relationship ||
                        "Candidate relationship"}
                    </b>
                  </div>
                );
              }
            )}
          </div>
        )}
      </Card>


      <Card>
        <div className="card-title">
          Reconstruction Classes
        </div>

        <div className="class-row">
          <span className="class-dot c0" />
          Verified Recovery
        </div>

        <div className="class-row">
          <span className="class-dot c1" />
          Structural Repair
        </div>

        <div className="class-row">
          <span className="class-dot c2" />
          Plausible Reconstruction
        </div>

        <div className="class-row">
          <span className="class-dot c3" />
          AI-Inferred Reconstruction
        </div>

        <div className="class-row">
          <span className="class-dot c4" />
          Insufficient Evidence
        </div>

        <div
          style={{
            marginTop: 14,
            fontSize: 12,
            color: "#64748b",
          }}
        >
          AI-inferred reconstruction must
          always be treated as estimated content,
          not verified original evidence.
        </div>
      </Card>
    </div>
  );
}
