import React, { useState } from "react";
import {
  UploadCloud,
  FileImage,
  ShieldCheck,
  ArrowRight,
  FileArchive,
  Database,
  Loader2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import Card from "../components/common/Card";
import Badge from "../components/common/Badge";

const API_URL = "http://127.0.0.1:8000";

export default function NewInvestigation() {
  const [name, setName] = useState(
    "IR-2026-014 — Damaged Storage Analysis"
  );

  const [source, setSource] = useState("Disk image (.img)");
  const [fileName, setFileName] = useState("No file selected");

  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [evidence, setEvidence] = useState(null);

  const navigate = useNavigate();

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    setSelectedFile(file);
    setFileName(file.name);
    setUploadError("");
    setEvidence(null);

    await uploadEvidence(file);
  };

  const uploadEvidence = async (file) => {
    setUploading(true);
    setUploadError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${API_URL}/api/evidence/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          errorText || `Upload failed with status ${response.status}`
        );
      }

      const data = await response.json();

      setEvidence(data);

      // Keep the real evidence information available
      // to the other frontend pages.
      localStorage.setItem(
        "recoverai_current_evidence",
        JSON.stringify(data)
      );

      localStorage.setItem(
        "recoverai_investigation",
        JSON.stringify({
          name,
          source,
          filename: file.name,
        })
      );

    } catch (error) {
      console.error("Evidence upload failed:", error);

      setUploadError(
        error.message ||
          "Unable to connect to the RECOVERAI backend."
      );
    } finally {
      setUploading(false);
    }
  };

  const handleStartAnalysis = async () => {
    if (!evidence?.evidence_id) {
      setUploadError("Please upload an evidence file first.");
      return;
    }

    try {
      setUploading(true);
      setUploadError("");

      // Start the backend scanner.
      const response = await fetch(
        `${API_URL}/api/analysis/scan/${evidence.evidence_id}`
      );

      if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
          errorText ||
            `Analysis failed with status ${response.status}`
        );
      }

      const analysisResult = await response.json();

      localStorage.setItem(
        "recoverai_analysis_result",
        JSON.stringify(analysisResult)
      );

      navigate("/analysis", {
        state: {
          evidence,
          analysis: analysisResult,
        },
      });

    } catch (error) {
      console.error("Analysis failed:", error);

      setUploadError(
        error.message ||
          "Unable to start backend analysis."
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="form-layout">
      {/* Header */}
      <div>
        <span className="eyebrow">EVIDENCE INTAKE</span>

        <h2>New Investigation</h2>

        <p className="muted">
          Create a read-only forensic evidence workspace before
          analysis begins.
        </p>
      </div>

      {/* Investigation Information */}
      <Card>
        <div className="form-grid">
          <label>
            Investigation name

            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter investigation name"
            />
          </label>

          <label>
            Evidence source

            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
            >
              <option>Disk image (.img)</option>
              <option>Raw image (.dd)</option>
              <option>Raw image (.raw)</option>
              <option>Binary dataset</option>
              <option>Corrupted file set</option>
            </select>
          </label>

          <label className="full">
            Description

            <textarea
              defaultValue="Controlled demo dataset containing intact, fragmented, corrupted and missing-fragment evidence."
            />
          </label>
        </div>
      </Card>

      {/* Upload */}
      <Card className="upload-zone">
        {uploading ? (
          <Loader2 size={32} className="spin" />
        ) : (
          <UploadCloud size={32} />
        )}

        <h3>
          {uploading
            ? "Processing evidence..."
            : "Drop evidence here"}
        </h3>

        <p>
          Supported: .img, .dd, .raw, binary and controlled
          corruption datasets
        </p>

        <input
          id="evidence-file"
          type="file"
          hidden
          accept=".img,.dd,.raw,.bin,.zip,.jpg,.jpeg,.png,.pdf"
          onChange={handleFileChange}
        />

        <label
          htmlFor="evidence-file"
          className="secondary-btn"
        >
          <UploadCloud size={16} />
          Choose Evidence File
        </label>

        <div className="selected-file">
          <FileImage size={17} />

          <span>{fileName}</span>

          {uploading && (
            <Badge tone="info">UPLOADING</Badge>
          )}

          {!uploading && evidence && (
            <Badge tone="success">UPLOADED</Badge>
          )}

          {!uploading && !evidence && selectedFile && (
            <Badge tone="warning">READY</Badge>
          )}
        </div>

        {uploadError && (
          <div
            style={{
              marginTop: "12px",
              padding: "10px 12px",
              borderRadius: "8px",
              background: "#fff1f2",
              color: "#be123c",
              fontSize: "13px",
            }}
          >
            {uploadError}
          </div>
        )}
      </Card>

      {/* Evidence Record */}
      <div className="evidence-intake">
        <Card>
          <div className="card-title">
            <span>Evidence Record</span>

            <Badge tone="info">READ ONLY</Badge>
          </div>

          <div className="record-grid">
            <div>
              <small>Evidence ID</small>
              <b>
                {evidence?.evidence_id || "Awaiting upload"}
              </b>
            </div>

            <div>
              <small>Filename</small>
              <b>
                {evidence?.filename || fileName}
              </b>
            </div>

            <div>
              <small>Size</small>
              <b>
                {evidence
                  ? `${evidence.size_bytes} bytes`
                  : "—"}
              </b>
            </div>

            <div>
              <small>SHA-256</small>

              <b className="mono">
                {evidence?.sha256 || "Awaiting upload"}
              </b>
            </div>

            <div>
              <small>Acquisition</small>

              <b>
                {evidence
                  ? new Date().toLocaleString()
                  : "—"}
              </b>
            </div>

            <div>
              <small>Source</small>

              <b>{source}</b>
            </div>
          </div>
        </Card>
      </div>

      {/* Evidence integrity information */}
      <div className="intake-info-grid">
        <Card>
          <div className="intake-info-item">
            <div className="intake-info-icon">
              <ShieldCheck size={19} />
            </div>

            <div>
              <b>Original Evidence Protected</b>

              <p>
                The original evidence remains read-only during
                analysis.
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="intake-info-item">
            <div className="intake-info-icon">
              <Database size={19} />
            </div>

            <div>
              <b>Working Copy Analysis</b>

              <p>
                Recovery operations are performed on a separate
                working copy.
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="intake-info-item">
            <div className="intake-info-icon">
              <FileArchive size={19} />
            </div>

            <div>
              <b>Forensic Preservation</b>

              <p>
                Source metadata and integrity information are
                preserved for analysis.
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Actions */}
      <div className="form-actions">
        <div className="security-note">
          <ShieldCheck size={16} />

          <span>
            Original evidence remains unchanged; analysis
            operates on a working copy.
          </span>
        </div>

        <button
          className="primary-btn"
          onClick={handleStartAnalysis}
          disabled={
            uploading ||
            !evidence?.evidence_id
          }
        >
          {uploading ? (
            <>
              Processing
              <Loader2 size={17} className="spin" />
            </>
          ) : (
            <>
              Start Analysis
              <ArrowRight size={17} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}