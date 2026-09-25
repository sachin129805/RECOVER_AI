import React, { useEffect, useRef, useState } from "react";
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  LoaderCircle,
  Trash2,
  Play,
  ShieldCheck,
  Files,
  MousePointerClick,
} from "lucide-react";

import Card from "../components/common/Card";
import Badge from "../components/common/Badge";

import {
  uploadEvidence,
  createInvestigation,
  getInvestigation,
  getInvestigationEvidence,
  attachEvidenceToInvestigation,
  analyzeInvestigation,
} from "../api";


/* =========================================================
   HELPERS
   ========================================================= */

function formatBytes(value) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
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


function shortenHash(hash) {
  if (!hash) {
    return "—";
  }

  if (hash.length <= 22) {
    return hash;
  }

  return `${hash.slice(0, 12)}…${hash.slice(-8)}`;
}


/* =========================================================
   PAGE
   ========================================================= */

export default function NewInvestigation() {
  const fileInputRef = useRef(null);

  const [investigationName, setInvestigationName] =
    useState("");

  const [description, setDescription] =
    useState("");

  const [source, setSource] =
    useState("Digital Evidence");

  const [selectedFiles, setSelectedFiles] =
    useState([]);

  const [uploadedEvidence, setUploadedEvidence] =
    useState([]);

  const [uploading, setUploading] =
    useState(false);

  const [uploadProgress, setUploadProgress] =
    useState(0);

  const [error, setError] =
    useState("");

  const [message, setMessage] =
    useState("");

  const [startingAnalysis, setStartingAnalysis] =
    useState(false);

  const [investigationId, setInvestigationId] =
    useState(
      () =>
        localStorage.getItem(
          "recoverai_investigation_id"
        ) || ""
    );


  /* =========================================================
     RESTORE INVESTIGATION
     ========================================================= */

  useEffect(() => {
    try {
      const storedCollection =
        localStorage.getItem(
          "recoverai_evidence_collection"
        );

      const storedInvestigation =
        localStorage.getItem(
          "recoverai_investigation"
        );

      if (storedCollection) {
        const parsed =
          JSON.parse(storedCollection);

        if (Array.isArray(parsed)) {
          setUploadedEvidence(parsed);
        }
      }

      if (storedInvestigation) {
        const parsed =
          JSON.parse(storedInvestigation);

        if (parsed.name) {
          setInvestigationName(parsed.name);
        }

        if (parsed.description) {
          setDescription(parsed.description);
        }

        if (parsed.source) {
          setSource(parsed.source);
        }

        if (parsed.investigation_id) {
          setInvestigationId(
            parsed.investigation_id
          );
        }
      }

      const storedInvestigationId =
        localStorage.getItem(
          "recoverai_investigation_id"
        );

      if (storedInvestigationId) {
        setInvestigationId(
          storedInvestigationId
        );
      }

      /*
       * If no previous investigation exists,
       * create a clean generic name.
       */
      if (!storedInvestigation) {
        setInvestigationName(
          `IR-${new Date().getFullYear()} — Digital Evidence Investigation`
        );
      }
    } catch (err) {
      console.error(
        "Unable to restore investigation:",
        err
      );
    }
  }, []);


  /* =========================================================
     SELECT FILES
     ========================================================= */

  const handleFileSelection = (event) => {
    const files = Array.from(
      event.target.files || []
    );

    if (!files.length) {
      return;
    }

    setError("");
    setMessage("");

    setSelectedFiles((previous) => {
      const existing = new Set(
        previous.map(
          (file) =>
            `${file.name}-${file.size}-${file.lastModified}`
        )
      );

      const additions = files.filter(
        (file) =>
          !existing.has(
            `${file.name}-${file.size}-${file.lastModified}`
          )
      );

      return [
        ...previous,
        ...additions,
      ];
    });

    /*
     * Allows selecting the same file again later.
     */
    event.target.value = "";
  };


  /* =========================================================
     REMOVE PENDING FILE
     ========================================================= */

  const removeSelectedFile = (index) => {
    setSelectedFiles((previous) =>
      previous.filter(
        (_, i) => i !== index
      )
    );
  };


  /* =========================================================
     CLEAR PENDING FILES
     ========================================================= */

  const clearSelectedFiles = () => {
    setSelectedFiles([]);
    setError("");
    setMessage("");
  };


  /* =========================================================
     UPLOAD MULTIPLE FILES
     ========================================================= */

  const handleUpload = async () => {
    if (!selectedFiles.length) {
      setError(
        "Select at least one evidence file."
      );
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setError("");
    setMessage("");

    const successfulUploads = [];
    const failedUploads = [];

    for (
      let index = 0;
      index < selectedFiles.length;
      index += 1
    ) {
      const file =
        selectedFiles[index];

      try {
        const result =
          await uploadEvidence(file);

        successfulUploads.push(result);
      } catch (err) {
        failedUploads.push({
          filename: file.name,
          error:
            err.message ||
            "Upload failed.",
        });
      }

      setUploadProgress(
        Math.round(
          ((index + 1) /
            selectedFiles.length) *
            100
        )
      );
    }


    /* -------------------------------------------------------
       SAVE COLLECTION
       ------------------------------------------------------- */

    if (successfulUploads.length) {
      setUploadedEvidence((previous) => {
        const existingIds = new Set(
          previous.map(
            (item) =>
              item.evidence_id
          )
        );

        const additions =
          successfulUploads.filter(
            (item) =>
              !existingIds.has(
                item.evidence_id
              )
          );

        const combined = [
          ...previous,
          ...additions,
        ];

        localStorage.setItem(
          "recoverai_evidence_collection",
          JSON.stringify(combined)
        );

        /*
         * Keep the first newly uploaded file
         * as the active evidence.
         */
        const active =
          additions[0] ||
          combined[0];

        if (active) {
          localStorage.setItem(
            "recoverai_current_evidence",
            JSON.stringify(active)
          );
        }

        return combined;
      });
    }


    /* -------------------------------------------------------
       RESULT MESSAGE
       ------------------------------------------------------- */

    if (!failedUploads.length) {
      setMessage(
        `${successfulUploads.length} evidence file${
          successfulUploads.length === 1
            ? ""
            : "s"
        } uploaded successfully.`
      );
    } else {
      setMessage(
        `${successfulUploads.length} uploaded successfully, ${failedUploads.length} failed.`
      );

      setError(
        failedUploads
          .map(
            (item) =>
              `${item.filename}: ${item.error}`
          )
          .join("\n")
      );
    }


    /*
     * Keep only failed files in the pending list.
     */
    const failedNames = new Set(
      failedUploads.map(
        (item) =>
          item.filename
      )
    );

    setSelectedFiles((previous) =>
      previous.filter(
        (file) =>
          failedNames.has(
            file.name
          )
      )
    );

    setUploading(false);
  };


  /* =========================================================
     SAVE INVESTIGATION
     ========================================================= */

  const saveInvestigation = async () => {
    const payload = {
      name:
        investigationName.trim() ||
        "RECOVERAI Investigation",
      description:
        description.trim(),
      source:
        source.trim() ||
        "Digital Evidence",
    };

    let activeId =
      investigationId ||
      localStorage.getItem(
        "recoverai_investigation_id"
      ) ||
      "";

    let investigation = null;

    if (activeId) {
      try {
        investigation =
          await getInvestigation(activeId);
      } catch {
        activeId = "";
      }
    }

    if (!activeId) {
      investigation =
        await createInvestigation(payload);

      activeId =
        investigation?.investigation_id ||
        investigation?.id ||
        "";

      if (!activeId) {
        throw new Error(
          "Backend did not return an investigation ID."
        );
      }
    }

    const currentEvidence =
      await getInvestigationEvidence(activeId);

    const existingIds = new Set(
      (Array.isArray(currentEvidence)
        ? currentEvidence
        : currentEvidence?.evidence || []
      ).map(
        (item) => item.evidence_id
      )
    );

    for (const item of uploadedEvidence) {
      if (!existingIds.has(item.evidence_id)) {
        await attachEvidenceToInvestigation(
          activeId,
          item.evidence_id
        );
      }
    }

    const persisted = {
      ...payload,
      investigation_id: activeId,
      evidence_count:
        uploadedEvidence.length,
      evidence_ids:
        uploadedEvidence.map(
          (item) => item.evidence_id
        ),
      updated_at:
        new Date().toISOString(),
    };

    setInvestigationId(activeId);

    localStorage.setItem(
      "recoverai_investigation_id",
      activeId
    );

    localStorage.setItem(
      "recoverai_investigation",
      JSON.stringify(persisted)
    );

    return {
      ...(investigation || {}),
      ...persisted,
      investigation_id: activeId,
    };
  };


  /* =========================================================
     START ANALYSIS
     ========================================================= */

  const handleStartAnalysis = async () => {
    if (!uploadedEvidence.length) {
      setError(
        "Upload at least one evidence file before starting analysis."
      );
      return;
    }

    setStartingAnalysis(true);
    setError("");
    setMessage("");

    try {
      const investigation =
        await saveInvestigation();

      const activeEvidence =
        uploadedEvidence.find(
          (item) =>
            item.evidence_id ===
            activeEvidenceId
        ) || uploadedEvidence[0];

      if (activeEvidence) {
        localStorage.setItem(
          "recoverai_current_evidence",
          JSON.stringify(activeEvidence)
        );
      }

      const result =
        await analyzeInvestigation(
          investigation.investigation_id
        );

      localStorage.setItem(
        "recoverai_investigation_analysis",
        JSON.stringify(result)
      );

      localStorage.setItem(
        "recoverai_analysis_result",
        JSON.stringify(result)
      );

      window.location.href =
        "/analysis";
    } catch (err) {
      console.error(
        "Unable to start investigation analysis:",
        err
      );

      setError(
        err.message ||
          "Unable to start investigation analysis."
      );

      setStartingAnalysis(false);
    }
  };

  /* =========================================================
     MAKE ACTIVE
     ========================================================= */

  const makeActiveEvidence = (
    evidence
  ) => {
    localStorage.setItem(
      "recoverai_current_evidence",
      JSON.stringify(evidence)
    );

    localStorage.removeItem(
      "recoverai_analysis_result"
    );

    localStorage.removeItem(
      "recoverai_reconstruction_result"
    );

    setMessage(
      `${evidence.filename} is now the active evidence artifact.`
    );
  };


  /* =========================================================
     REMOVE STORED EVIDENCE FROM COLLECTION
     ========================================================= */

  const removeUploadedEvidence = (
    evidenceId
  ) => {
    const updated =
      uploadedEvidence.filter(
        (item) =>
          item.evidence_id !==
          evidenceId
      );

    setUploadedEvidence(
      updated
    );

    localStorage.setItem(
      "recoverai_evidence_collection",
      JSON.stringify(updated)
    );

    const stored =
      localStorage.getItem(
        "recoverai_current_evidence"
      );

    if (stored) {
      try {
        const current =
          JSON.parse(stored);

        if (
          current.evidence_id ===
          evidenceId
        ) {
          if (updated.length) {
            localStorage.setItem(
              "recoverai_current_evidence",
              JSON.stringify(
                updated[0]
              )
            );
          } else {
            localStorage.removeItem(
              "recoverai_current_evidence"
            );
          }
        }
      } catch {
        // Ignore invalid local state.
      }
    }
  };


  /* =========================================================
     ACTIVE EVIDENCE
     ========================================================= */

  let activeEvidenceId = null;

  try {
    const stored =
      localStorage.getItem(
        "recoverai_current_evidence"
      );

    if (stored) {
      activeEvidenceId =
        JSON.parse(
          stored
        )?.evidence_id || null;
    }
  } catch {
    activeEvidenceId = null;
  }


  /* =========================================================
     STYLES
     ========================================================= */

  const inputStyle = {
    width: "100%",
    boxSizing: "border-box",
    border: "1px solid #dbe3ec",
    borderRadius: "8px",
    background: "#ffffff",
    color: "#0f172a",
    padding: "11px 13px",
    fontFamily: "inherit",
    fontSize: "13px",
    outline: "none",
  };

  const labelStyle = {
    display: "block",
    marginBottom: "7px",
    fontSize: "11px",
    fontWeight: 700,
    color: "#475569",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  };

  const buttonStyle = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "7px",
    borderRadius: "8px",
    padding: "9px 14px",
    border: "1px solid #d7e0ea",
    background: "#ffffff",
    color: "#334155",
    fontFamily: "inherit",
    fontSize: "12px",
    fontWeight: 600,
    cursor: "pointer",
  };

  const primaryButtonStyle = {
    ...buttonStyle,
    background: "#0284c7",
    borderColor: "#0284c7",
    color: "#ffffff",
  };


  /* =========================================================
     RENDER
     ========================================================= */

  return (
    <div>
      {/* =====================================================
          HEADER
          ===================================================== */}

      <div className="page-intro">
        <div>
          <span className="eyebrow">
            INVESTIGATION INTAKE
          </span>

          <h2>
            New Investigation
          </h2>

          <p>
            Create an investigation and
            upload one or more digital
            evidence artifacts for analysis.
          </p>
        </div>

        <Badge tone="info">
          {uploadedEvidence.length}{" "}
          EVIDENCE{" "}
          {uploadedEvidence.length === 1
            ? "ITEM"
            : "ITEMS"}
        </Badge>
      </div>


      {/* =====================================================
          ERROR
          ===================================================== */}

      {error && (
        <Card>
          <div className="contradiction">
            <AlertTriangle
              size={18}
            />

            <div>
              <b>
                Investigation Error
              </b>

              <p
                style={{
                  whiteSpace:
                    "pre-line",
                }}
              >
                {error}
              </p>
            </div>
          </div>
        </Card>
      )}


      {/* =====================================================
          SUCCESS
          ===================================================== */}

      {message && (
        <Card>
          <div className="contradiction">
            <CheckCircle2
              size={18}
            />

            <div>
              <b>
                Investigation Updated
              </b>

              <p>
                {message}
              </p>
            </div>
          </div>
        </Card>
      )}


      {/* =====================================================
          DETAILS
          ===================================================== */}

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "minmax(0, 1.5fr) minmax(260px, 0.7fr)",
          gap: "18px",
          marginBottom: "18px",
        }}
      >
        <Card>
          <div className="card-title">
            Investigation Details
          </div>

          <div
            style={{
              marginBottom: "18px",
            }}
          >
            <label style={labelStyle}>
              Investigation Name
            </label>

            <input
              type="text"
              value={
                investigationName
              }
              onChange={(event) =>
                setInvestigationName(
                  event.target.value
                )
              }
              placeholder="Enter investigation name"
              style={inputStyle}
            />
          </div>

          <div
            style={{
              marginBottom: "18px",
            }}
          >
            <label style={labelStyle}>
              Case Description
            </label>

            <textarea
              value={
                description
              }
              onChange={(event) =>
                setDescription(
                  event.target.value
                )
              }
              placeholder="Describe the evidence and investigation context"
              rows={4}
              style={{
                ...inputStyle,
                resize: "vertical",
              }}
            />
          </div>

          <div>
            <label style={labelStyle}>
              Evidence Source
            </label>

            <input
              type="text"
              value={source}
              onChange={(event) =>
                setSource(
                  event.target.value
                )
              }
              placeholder="Digital Evidence"
              style={inputStyle}
            />
          </div>
        </Card>


        {/* ===================================================
            SUMMARY
            =================================================== */}

        <Card>
          <div className="card-title">
            Investigation Summary
          </div>

          <div className="metric-line">
            <span>
              Evidence items
            </span>

            <b>
              {uploadedEvidence.length}
            </b>
          </div>

          <div className="metric-line">
            <span>
              Pending uploads
            </span>

            <b>
              {selectedFiles.length}
            </b>
          </div>

          <div className="metric-line">
            <span>
              Active evidence
            </span>

            <b>
              {activeEvidenceId
                ? "Selected"
                : "None"}
            </b>
          </div>

          <div className="metric-line">
            <span>
              Investigation ID
            </span>

            <b
              style={{
                fontFamily: "monospace",
                fontSize: "10px",
              }}
            >
              {investigationId || "Not created"}
            </b>
          </div>

          <div
            style={{
              marginTop: "18px",
            }}
          >
            <Badge
              tone={
                uploadedEvidence.length
                  ? "success"
                  : "info"
              }
            >
              {uploadedEvidence.length
                ? "EVIDENCE READY"
                : "AWAITING EVIDENCE"}
            </Badge>
          </div>
        </Card>
      </div>


      {/* =====================================================
          MULTI-FILE UPLOAD
          ===================================================== */}

      <Card>
        <div className="card-title">
          <span>
            Evidence Upload
          </span>

          <span
            style={{
              fontSize: "11px",
              color: "#64748b",
            }}
          >
            Multiple files supported
          </span>
        </div>

        <div
          onClick={() =>
            fileInputRef.current?.click()
          }
          style={{
            border:
              "1px dashed #b8c6d6",
            borderRadius: "12px",
            background: "#f8fafc",
            padding: "38px 24px",
            textAlign: "center",
            cursor: "pointer",
          }}
        >
          <Upload
            size={30}
            style={{
              color: "#0284c7",
              marginBottom: "10px",
            }}
          />

          <h3
            style={{
              margin:
                "4px 0 7px",
              color: "#0f172a",
            }}
          >
            Add Evidence Files
          </h3>

          <p
            style={{
              margin:
                "0 auto 14px",
              maxWidth: "520px",
              color: "#64748b",
              fontSize: "12px",
            }}
          >
            Select one or multiple evidence
            artifacts. Any file type can be
            submitted.
          </p>

          <span
            style={{
              ...buttonStyle,
              pointerEvents: "none",
            }}
          >
            <Files size={15} />
            Browse Files
          </span>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={
            handleFileSelection
          }
          style={{
            display: "none",
          }}
        />


        {/* ===================================================
            PENDING FILES
            =================================================== */}

        {selectedFiles.length > 0 && (
          <div
            style={{
              marginTop: "22px",
            }}
          >
            <div
              className="card-title"
              style={{
                marginBottom: "12px",
              }}
            >
              <span>
                Pending Uploads
              </span>

              <button
                type="button"
                style={buttonStyle}
                onClick={
                  clearSelectedFiles
                }
                disabled={uploading}
              >
                Clear
              </button>
            </div>

            <div
              style={{
                display: "grid",
                gap: "9px",
              }}
            >
              {selectedFiles.map(
                (file, index) => (
                  <div
                    key={`${file.name}-${file.size}-${file.lastModified}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent:
                        "space-between",
                      gap: "15px",
                      padding:
                        "11px 13px",
                      border:
                        "1px solid #e2e8f0",
                      borderRadius: "9px",
                      background:
                        "#ffffff",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems:
                          "center",
                        gap: "11px",
                        minWidth: 0,
                      }}
                    >
                      <FileText
                        size={18}
                        style={{
                          color:
                            "#0284c7",
                          flexShrink: 0,
                        }}
                      />

                      <div
                        style={{
                          minWidth: 0,
                        }}
                      >
                        <strong
                          style={{
                            display:
                              "block",
                            color:
                              "#0f172a",
                            fontSize:
                              "12px",
                            overflow:
                              "hidden",
                            textOverflow:
                              "ellipsis",
                            whiteSpace:
                              "nowrap",
                          }}
                        >
                          {file.name}
                        </strong>

                        <span
                          style={{
                            color:
                              "#64748b",
                            fontSize:
                              "11px",
                          }}
                        >
                          {formatBytes(
                            file.size
                          )}
                        </span>
                      </div>
                    </div>

                    <button
                      type="button"
                      style={{
                        ...buttonStyle,
                        padding:
                          "7px 9px",
                      }}
                      onClick={() =>
                        removeSelectedFile(
                          index
                        )
                      }
                      disabled={
                        uploading
                      }
                    >
                      <Trash2
                        size={14}
                      />
                    </button>
                  </div>
                )
              )}
            </div>


            {/* Progress */}

            {uploading && (
              <div
                style={{
                  marginTop:
                    "18px",
                }}
              >
                <div
                  style={{
                    display:
                      "flex",
                    justifyContent:
                      "space-between",
                    marginBottom:
                      "7px",
                    fontSize:
                      "11px",
                    color:
                      "#64748b",
                  }}
                >
                  <span>
                    Uploading evidence...
                  </span>

                  <b>
                    {uploadProgress}%
                  </b>
                </div>

                <div
                  style={{
                    height: "5px",
                    borderRadius:
                      "999px",
                    background:
                      "#e2e8f0",
                    overflow:
                      "hidden",
                  }}
                >
                  <div
                    style={{
                      width:
                        `${uploadProgress}%`,
                      height: "100%",
                      background:
                        "#0284c7",
                      transition:
                        "width 0.2s ease",
                    }}
                  />
                </div>
              </div>
            )}


            <div
              style={{
                display: "flex",
                justifyContent:
                  "flex-end",
                marginTop: "16px",
              }}
            >
              <button
                type="button"
                style={{
                  ...primaryButtonStyle,
                  opacity:
                    uploading
                      ? 0.6
                      : 1,
                }}
                onClick={
                  handleUpload
                }
                disabled={
                  uploading ||
                  !selectedFiles.length
                }
              >
                {uploading ? (
                  <>
                    <LoaderCircle
                      size={15}
                      style={{
                        animation:
                          "spin 0.9s linear infinite",
                      }}
                    />
                    Uploading
                  </>
                ) : (
                  <>
                    <Upload
                      size={15}
                    />
                    Upload{" "}
                    {
                      selectedFiles.length
                    }{" "}
                    File
                    {selectedFiles.length ===
                    1
                      ? ""
                      : "s"}
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </Card>


      {/* =====================================================
          EVIDENCE COLLECTION
          ===================================================== */}

      <Card>
        <div className="card-title">
          <span>
            Evidence Collection
          </span>

          <Badge tone="info">
            {uploadedEvidence.length}
          </Badge>
        </div>

        {uploadedEvidence.length ===
        0 ? (
          <div
            style={{
              padding: "32px",
              textAlign: "center",
            }}
          >
            <ShieldCheck
              size={28}
              style={{
                color: "#64748b",
              }}
            />

            <h3
              style={{
                margin:
                  "10px 0 6px",
              }}
            >
              No Evidence Uploaded
            </h3>

            <p
              style={{
                margin: 0,
                color: "#64748b",
                fontSize: "12px",
              }}
            >
              Uploaded evidence artifacts
              will appear here with their
              forensic identifiers and
              SHA-256 hashes.
            </p>
          </div>
        ) : (
          <div
            style={{
              overflowX:
                "auto",
            }}
          >
            <table
              style={{
                width: "100%",
                borderCollapse:
                  "collapse",
              }}
            >
              <thead>
                <tr>
                  {[
                    "Evidence",
                    "Size",
                    "SHA-256",
                    "Evidence ID",
                    "Status",
                    "Action",
                  ].map((heading) => (
                    <th
                      key={heading}
                      style={{
                        padding:
                          "10px 12px",
                        textAlign:
                          "left",
                        fontSize:
                          "10px",
                        color:
                          "#64748b",
                        background:
                          "#f8fafc",
                        borderBottom:
                          "1px solid #e2e8f0",
                        textTransform:
                          "uppercase",
                        letterSpacing:
                          "0.04em",
                      }}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {uploadedEvidence.map(
                  (item) => {
                    const isActive =
                      item.evidence_id ===
                      activeEvidenceId;

                    return (
                      <tr
                        key={
                          item.evidence_id
                        }
                      >
                        <td
                          style={{
                            padding:
                              "12px",
                            borderBottom:
                              "1px solid #edf2f7",
                          }}
                        >
                          <div
                            style={{
                              display:
                                "flex",
                              alignItems:
                                "center",
                              gap:
                                "9px",
                            }}
                          >
                            <FileText
                              size={16}
                              style={{
                                color:
                                  "#0284c7",
                              }}
                            />

                            <div>
                              <strong
                                style={{
                                  display:
                                    "block",
                                  fontSize:
                                    "12px",
                                }}
                              >
                                {
                                  item.filename
                                }
                              </strong>

                              {isActive && (
                                <small
                                  style={{
                                    color:
                                      "#0284c7",
                                    fontSize:
                                      "10px",
                                  }}
                                >
                                  Active evidence
                                </small>
                              )}
                            </div>
                          </div>
                        </td>

                        <td
                          style={{
                            padding:
                              "12px",
                            fontSize:
                              "12px",
                            borderBottom:
                              "1px solid #edf2f7",
                          }}
                        >
                          {formatBytes(
                            item.size_bytes
                          )}
                        </td>

                        <td
                          style={{
                            padding:
                              "12px",
                            fontFamily:
                              "monospace",
                            fontSize:
                              "10px",
                            borderBottom:
                              "1px solid #edf2f7",
                          }}
                        >
                          {shortenHash(
                            item.sha256
                          )}
                        </td>

                        <td
                          style={{
                            padding:
                              "12px",
                            fontFamily:
                              "monospace",
                            fontSize:
                              "10px",
                            borderBottom:
                              "1px solid #edf2f7",
                          }}
                        >
                          {
                            item.evidence_id
                          }
                        </td>

                        <td
                          style={{
                            padding:
                              "12px",
                            borderBottom:
                              "1px solid #edf2f7",
                          }}
                        >
                          <Badge
                            tone={
                              isActive
                                ? "success"
                                : "info"
                            }
                          >
                            {isActive
                              ? "ACTIVE"
                              : "STORED"}
                          </Badge>
                        </td>

                        <td
                          style={{
                            padding:
                              "12px",
                            borderBottom:
                              "1px solid #edf2f7",
                          }}
                        >
                          <div
                            style={{
                              display:
                                "flex",
                              gap:
                                "6px",
                            }}
                          >
                            {!isActive && (
                              <button
                                type="button"
                                style={{
                                  ...buttonStyle,
                                  padding:
                                    "6px 9px",
                                  fontSize:
                                    "10px",
                                }}
                                onClick={() =>
                                  makeActiveEvidence(
                                    item
                                  )
                                }
                              >
                                <MousePointerClick
                                  size={
                                    13
                                  }
                                />
                                Select
                              </button>
                            )}

                            <button
                              type="button"
                              style={{
                                ...buttonStyle,
                                padding:
                                  "6px 8px",
                              }}
                              onClick={() =>
                                removeUploadedEvidence(
                                  item.evidence_id
                                )
                              }
                            >
                              <Trash2
                                size={
                                  13
                                }
                              />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  }
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>


      {/* =====================================================
          ANALYSIS
          ===================================================== */}

      <Card>
        <div className="card-title">
          <span>
            Ready for Analysis
          </span>

          <Badge
            tone={
              uploadedEvidence.length
                ? "success"
                : "info"
            }
          >
            {uploadedEvidence.length
              ? "READY"
              : "AWAITING EVIDENCE"}
          </Badge>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent:
              "space-between",
            gap: "20px",
            flexWrap:
              "wrap",
          }}
        >
          <div>
            <h3
              style={{
                margin:
                  "0 0 5px",
                fontSize:
                  "14px",
              }}
            >
              {uploadedEvidence.length
                ? `${uploadedEvidence.length} evidence item${
                    uploadedEvidence.length ===
                    1
                      ? ""
                      : "s"
                  } in this investigation`
                : "Upload evidence to continue"}
            </h3>

            <p
              style={{
                margin: 0,
                color: "#64748b",
                fontSize:
                  "12px",
              }}
            >
              The original uploaded artifacts
              remain unchanged. The investigation
              is persisted in the backend and all
              attached evidence is analyzed together.
            </p>
          </div>

          <button
            type="button"
            style={{
              ...primaryButtonStyle,
              opacity:
                startingAnalysis ||
                !uploadedEvidence.length
                  ? 0.55
                  : 1,
            }}
            onClick={
              handleStartAnalysis
            }
            disabled={
              startingAnalysis ||
              !uploadedEvidence.length
            }
          >
            {startingAnalysis ? (
              <>
                <LoaderCircle
                  size={16}
                  style={{
                    animation:
                      "spin 0.9s linear infinite",
                  }}
                />
                Starting Analysis
              </>
            ) : (
              <>
                <Play
                  size={16}
                />
                Start Analysis
              </>
            )}
          </button>
        </div>
      </Card>


      {/* =====================================================
          LOCAL SPINNER
          ===================================================== */}

      <style>
        {`
          @keyframes spin {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }
        `}
      </style>
    </div>
  );
}
