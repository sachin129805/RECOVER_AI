import React, { useMemo, useState } from "react";
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  FileSearch,
  LoaderCircle,
  Send,
  ShieldCheck,
  Sparkles,
  User,
  X,
  AlertCircle,
} from "lucide-react";

import { askCopilotQuestion } from "../../api";

function formatValue(value, fallback = "Not available") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return value;
}

function getAnswerText(payload) {
  if (!payload) {
    return "The backend returned no response.";
  }

  if (typeof payload.answer !== "string") {
    return (
      payload.answer?.text ||
      payload.answer?.answer ||
      "The backend returned a structured response without explanatory text."
    );
  }

  try {
    const parsed = JSON.parse(payload.answer);

    return (
      parsed?.text ||
      parsed?.answer ||
      parsed?.summary ||
      payload.answer
    );
  } catch {
    return payload.answer;
  }
}

function getSupportPoints(payload, evidenceMeta) {
  if (Array.isArray(payload?.evidence_references) && payload.evidence_references.length) {
    return payload.evidence_references.map(String);
  }

  return [
    `Evidence ID: ${evidenceMeta.id}`,
    `Recovery status: ${evidenceMeta.status}`,
    `Confidence: ${formatValue(evidenceMeta.confidence, "Not available")}%`,
  ];
}

export default function EvidenceCopilot({
  evidence,
  recoverySummary,
  onClose,
}) {
  const evidenceMeta = useMemo(() => {
    const id =
      evidence?.evidence_id ||
      evidence?.id ||
      "Unknown evidence";

    const name =
      evidence?.name ||
      evidence?.filename ||
      "Selected evidence";

    const type =
      evidence?.type ||
      evidence?.file_type ||
      "Unknown";

    const status =
      evidence?.status ||
      evidence?.recovery_status ||
      "Candidate";

    const confidence = Number.isFinite(Number(evidence?.confidence))
      ? Number(evidence.confidence)
      : Number.isFinite(Number(recoverySummary?.confidence))
        ? Number(recoverySummary.confidence)
        : null;

    return {
      id,
      name,
      type,
      status,
      confidence,
    };
  }, [evidence, recoverySummary]);

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [useOllama, setUseOllama] = useState(true);
  const [modelLabel, setModelLabel] = useState("Local AI");

  const [messages, setMessages] = useState([
    {
      role: "assistant",
      title: "Evidence Copilot ready",
      text: `I am analyzing ${evidenceMeta.name}. Ask about recovery confidence, fragments, integrity, missing data, provenance, or evidence priority.`,
      points: [
        `Selected evidence: ${evidenceMeta.id}`,
        `Recovery: ${evidenceMeta.status}`,
        `Confidence: ${formatValue(evidenceMeta.confidence, "Not available")}%`,
      ],
    },
  ]);

  const suggestions = useMemo(
    () => [
      `Why is the confidence ${formatValue(evidenceMeta.confidence, "not available")}%?`,
      "Explain the detected fragments",
      "What data is missing?",
      "Explain the integrity result",
    ],
    [evidenceMeta]
  );

  const askQuestion = async (value = question) => {
    const trimmed = String(value || "").trim();

    if (!trimmed || loading || !evidenceMeta.id) {
      return;
    }

    setMessages((previous) => [
      ...previous,
      {
        role: "user",
        text: trimmed,
      },
    ]);

    setQuestion("");
    setLoading(true);

    try {
      const payload = await askCopilotQuestion(
        evidenceMeta.id,
        trimmed,
        { useOllama }
      );

      const source = String(payload?.source || "").toLowerCase();
      const model = payload?.model;

      if (source === "ollama" && model) {
        setModelLabel(`Ollama · ${model}`);
      } else if (source === "ollama") {
        setModelLabel("Ollama");
      } else if (source === "deterministic-fallback") {
        setModelLabel("Evidence engine · Ollama fallback");
      } else if (source === "deterministic") {
        setModelLabel("Evidence engine");
      } else {
        setModelLabel("Local AI");
      }

      const text = getAnswerText(payload);
      const points = getSupportPoints(payload, evidenceMeta);

      const ollamaError = payload?.ollama_error;

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          title:
            source === "ollama"
              ? "AI-assisted forensic response"
              : source === "deterministic"
                ? "Evidence-grounded response"
                : source === "deterministic-fallback"
                  ? "Evidence-grounded response"
                  : "Evidence Copilot response",
          text,
          points,
          warning: ollamaError
            ? `Ollama fallback: ${ollamaError}`
            : null,
        },
      ]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          title: "Copilot error",
          text:
            error?.message ||
            "The Copilot request could not be completed.",
          points: [
            `Evidence ID: ${evidenceMeta.id}`,
            "The evidence context was not changed.",
          ],
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askQuestion();
    }
  };

  return (
    <aside
      className="evidence-copilot"
      style={{
        width: "390px",
        minWidth: "350px",
        height: "calc(100vh - 32px)",
        maxHeight: "calc(100vh - 32px)",
        margin: "16px 16px 16px 0",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        background: "#ffffff",
        border: "1px solid #dbe5ef",
        borderRadius: "16px",
        boxShadow: "0 18px 50px rgba(15, 23, 42, 0.12)",
        color: "#0f172a",
      }}
    >
      {/* HEADER */}
      <div
        style={{
          flex: "0 0 auto",
          padding: "15px 16px 13px",
          borderBottom: "1px solid #e8eef5",
          background:
            "linear-gradient(180deg, #ffffff 0%, #f8fbff 100%)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 11,
              minWidth: 0,
            }}
          >
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 11,
                display: "grid",
                placeItems: "center",
                background: "#eff6ff",
                border: "1px solid #bfdbfe",
                color: "#2563eb",
                flex: "0 0 auto",
              }}
            >
              <Bot size={19} />
            </div>

            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 750,
                  letterSpacing: "-0.01em",
                }}
              >
                Evidence Copilot
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  marginTop: 3,
                  fontSize: 10.5,
                  color: "#64748b",
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: useOllama ? "#22c55e" : "#94a3b8",
                  }}
                />
                {modelLabel}
              </div>
            </div>
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close Evidence Copilot"
              style={{
                width: 30,
                height: 30,
                display: "grid",
                placeItems: "center",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                background: "#ffffff",
                color: "#64748b",
                cursor: "pointer",
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* EVIDENCE CONTEXT */}
      <div
        style={{
          flex: "0 0 auto",
          margin: "12px",
          padding: "11px 12px",
          border: "1px solid #e2e8f0",
          borderRadius: 11,
          background: "#f8fafc",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 9,
          }}
        >
          <FileSearch size={16} color="#2563eb" />

          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              title={evidenceMeta.name}
              style={{
                fontSize: 11.5,
                fontWeight: 700,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {evidenceMeta.name}
            </div>

            <div
              style={{
                marginTop: 3,
                fontSize: 9.5,
                color: "#64748b",
              }}
            >
              {evidenceMeta.id} · {evidenceMeta.type}
            </div>
          </div>

          <div
            style={{
              textAlign: "right",
              paddingLeft: 8,
              borderLeft: "1px solid #e2e8f0",
            }}
          >
            <div
              style={{
                fontSize: 8,
                fontWeight: 700,
                color: "#94a3b8",
                letterSpacing: "0.06em",
              }}
            >
              CONFIDENCE
            </div>
            <div
              style={{
                marginTop: 2,
                fontSize: 13,
                fontWeight: 800,
                color: "#0f172a",
              }}
            >
              {formatValue(evidenceMeta.confidence, "—")}%
            </div>
          </div>
        </div>
      </div>

      {/* MESSAGES */}
      <div
        className="copilot-messages"
        style={{
          flex: "1 1 auto",
          minHeight: 0,
          overflowY: "auto",
          padding: "2px 13px 12px",
          scrollbarWidth: "thin",
        }}
      >
        {messages.map((message, index) => {
          const isUser = message.role === "user";

          return (
            <div
              key={`${message.role}-${index}`}
              style={{
                display: "flex",
                justifyContent: isUser ? "flex-end" : "flex-start",
                marginTop: 10,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  maxWidth: isUser ? "86%" : "96%",
                  flexDirection: isUser ? "row-reverse" : "row",
                }}
              >
                <div
                  style={{
                    width: 26,
                    height: 26,
                    flex: "0 0 26px",
                    display: "grid",
                    placeItems: "center",
                    borderRadius: 8,
                    background: isUser ? "#eff6ff" : "#f1f5f9",
                    border: "1px solid #e2e8f0",
                    color: isUser ? "#2563eb" : "#475569",
                  }}
                >
                  {isUser ? <User size={13} /> : <Bot size={13} />}
                </div>

                <div
                  style={{
                    padding: isUser ? "9px 11px" : "10px 11px",
                    borderRadius: isUser
                      ? "12px 12px 4px 12px"
                      : "4px 12px 12px 12px",
                    background: isUser ? "#eff6ff" : "#f8fafc",
                    border: "1px solid #e2e8f0",
                    minWidth: 0,
                  }}
                >
                  {message.title && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        marginBottom: 5,
                        fontSize: 11,
                        fontWeight: 750,
                        color: "#1e293b",
                      }}
                    >
                      {!isUser && <ShieldCheck size={12} color="#2563eb" />}
                      {message.title}
                    </div>
                  )}

                  <div
                    style={{
                      fontSize: 11.5,
                      lineHeight: 1.55,
                      color: "#334155",
                      whiteSpace: "pre-wrap",
                      overflowWrap: "anywhere",
                    }}
                  >
                    {message.text}
                  </div>

                  {message.points?.length > 0 && !isUser && (
                    <div
                      style={{
                        marginTop: 9,
                        paddingTop: 8,
                        borderTop: "1px solid #e2e8f0",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 5,
                          marginBottom: 5,
                          fontSize: 9,
                          fontWeight: 800,
                          color: "#64748b",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                        }}
                      >
                        <CheckCircle2 size={11} color="#16a34a" />
                        Supporting evidence
                      </div>

                      {message.points.map((point, pointIndex) => (
                        <div
                          key={pointIndex}
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 3,
                            fontSize: 9.5,
                            lineHeight: 1.45,
                            color: "#64748b",
                            marginTop: 3,
                          }}
                        >
                          <ChevronRight size={10} style={{ flex: "0 0 auto", marginTop: 2 }} />
                          <span>{point}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {message.warning && (
                    <div
                      style={{
                        display: "flex",
                        gap: 6,
                        marginTop: 8,
                        padding: "7px 8px",
                        borderRadius: 7,
                        background: "#fff7ed",
                        border: "1px solid #fed7aa",
                        color: "#9a3412",
                        fontSize: 9.5,
                        lineHeight: 1.4,
                      }}
                    >
                      <AlertCircle size={12} style={{ flex: "0 0 auto" }} />
                      <span>{message.warning}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {loading && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginTop: 10,
              padding: "9px 11px",
              borderRadius: 10,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              color: "#64748b",
              fontSize: 10.5,
            }}
          >
            <LoaderCircle size={14} className="spin" />
            Analyzing current evidence with {useOllama ? "local Ollama" : "the evidence engine"}…
          </div>
        )}
      </div>

      {/* AI MODE */}
      <div
        style={{
          flex: "0 0 auto",
          padding: "8px 13px",
          borderTop: "1px solid #e8eef5",
          background: "#fbfdff",
        }}
      >
        <label
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            fontSize: 10,
            color: "#475569",
            cursor: "pointer",
          }}
        >
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
            }}
          >
            <Sparkles size={12} color="#2563eb" />
            Use local Ollama for forensic reasoning
          </span>

          <input
            type="checkbox"
            checked={useOllama}
            onChange={(event) => setUseOllama(event.target.checked)}
            style={{
              accentColor: "#2563eb",
              cursor: "pointer",
            }}
          />
        </label>
      </div>

      {/* SUGGESTIONS */}
      <div
        style={{
          flex: "0 0 auto",
          padding: "8px 13px",
          borderTop: "1px solid #e8eef5",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            marginBottom: 6,
            fontSize: 9,
            fontWeight: 800,
            color: "#64748b",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          <Sparkles size={11} color="#2563eb" />
          Suggested questions
        </div>

        <div
          style={{
            display: "flex",
            gap: 5,
            overflowX: "auto",
            paddingBottom: 2,
          }}
        >
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              disabled={loading}
              onClick={() => askQuestion(suggestion)}
              style={{
                flex: "0 0 auto",
                maxWidth: 190,
                padding: "6px 8px",
                border: "1px solid #dbe5ef",
                borderRadius: 7,
                background: "#ffffff",
                color: "#475569",
                fontSize: 9.5,
                cursor: loading ? "default" : "pointer",
                textAlign: "left",
              }}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      {/* COMPOSER */}
      <div
        style={{
          flex: "0 0 auto",
          padding: "10px 13px 13px",
          borderTop: "1px solid #e8eef5",
          background: "#ffffff",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 7,
            padding: 5,
            border: "1px solid #cbd5e1",
            borderRadius: 11,
            background: "#ffffff",
            boxShadow: "0 2px 8px rgba(15, 23, 42, 0.04)",
          }}
        >
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about this evidence…"
            disabled={loading}
            rows={1}
            style={{
              flex: 1,
              minWidth: 0,
              minHeight: 34,
              maxHeight: 90,
              resize: "none",
              border: "none",
              outline: "none",
              background: "transparent",
              color: "#0f172a",
              fontFamily: "inherit",
              fontSize: 11.5,
              lineHeight: 1.45,
              padding: "8px 7px",
            }}
          />

          <button
            type="button"
            onClick={() => askQuestion()}
            disabled={!question.trim() || loading}
            aria-label="Send question"
            style={{
              width: 34,
              height: 34,
              flex: "0 0 34px",
              display: "grid",
              placeItems: "center",
              border: "none",
              borderRadius: 8,
              background:
                question.trim() && !loading
                  ? "#2563eb"
                  : "#e2e8f0",
              color:
                question.trim() && !loading
                  ? "#ffffff"
                  : "#94a3b8",
              cursor:
                question.trim() && !loading
                  ? "pointer"
                  : "default",
            }}
          >
            <Send size={15} />
          </button>
        </div>

        <div
          style={{
            marginTop: 5,
            textAlign: "center",
            fontSize: 8.5,
            color: "#94a3b8",
          }}
        >
          Enter to send · Shift + Enter for a new line · Ask multiple questions in one investigation
        </div>
      </div>
    </aside>
  );
}

