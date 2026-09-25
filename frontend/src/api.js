const API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

export async function apiFetch(path, options = {}) {
  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    }
  );

  if (!response.ok) {
    const text = await response.text().catch(() => "");

    let message = text;

    try {
      const parsed = JSON.parse(text);

      message =
        parsed.detail ||
        parsed.message ||
        text;
    } catch {
      // Keep raw response text.
    }

    throw new Error(
      message ||
        `Request failed with status ${response.status}`
    );
  }

  if (response.status === 204) {
    return null;
  }

  const contentType =
    response.headers.get("content-type") || "";

  if (
    contentType.includes(
      "application/json"
    )
  ) {
    return response.json();
  }

  return response.text();
}


/* =========================================================
   EVIDENCE
   ========================================================= */

export function uploadEvidence(file) {
  const formData = new FormData();

  formData.append(
    "file",
    file
  );

  return apiFetch(
    "/api/evidence/upload",
    {
      method: "POST",
      body: formData,
    }
  );
}


/* =========================================================
   INVESTIGATIONS
   ========================================================= */

export function createInvestigation(data) {
  return apiFetch(
    "/api/investigations",
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(data),
    }
  );
}


export function getInvestigation(
  investigationId
) {
  if (!investigationId) {
    throw new Error(
      "Investigation ID is required."
    );
  }

  return apiFetch(
    `/api/investigations/${encodeURIComponent(
      investigationId
    )}`
  );
}


export function attachEvidenceToInvestigation(
  investigationId,
  evidenceId
) {
  if (!investigationId) {
    throw new Error(
      "Investigation ID is required."
    );
  }

  if (!evidenceId) {
    throw new Error(
      "Evidence ID is required."
    );
  }

  return apiFetch(
    `/api/investigations/${encodeURIComponent(
      investigationId
    )}/evidence`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        evidence_id: evidenceId,
        role: "evidence",
      }),
    }
  );
}


export function getInvestigationEvidence(
  investigationId
) {
  if (!investigationId) {
    throw new Error(
      "Investigation ID is required."
    );
  }

  return apiFetch(
    `/api/investigations/${encodeURIComponent(
      investigationId
    )}/evidence`
  );
}


export function analyzeInvestigation(
  investigationId
) {
  if (!investigationId) {
    throw new Error(
      "Investigation ID is required."
    );
  }

  return apiFetch(
    `/api/investigations/${encodeURIComponent(
      investigationId
    )}/analyze`,
    {
      method: "POST",
    }
  );
}


export function getInvestigationFragments(
  investigationId
) {
  if (!investigationId) {
    throw new Error(
      "Investigation ID is required."
    );
  }

  return apiFetch(
    `/api/investigations/${encodeURIComponent(
      investigationId
    )}/fragments`
  );
}


export function analyzeInvestigationRelationships(
  investigationId
) {
  if (!investigationId) {
    throw new Error(
      "Investigation ID is required."
    );
  }

  return apiFetch(
    `/api/investigations/${encodeURIComponent(
      investigationId
    )}/relationships`,
    {
      method: "POST",
    }
  );
}


export function getInvestigationRelationships(
  investigationId
) {
  if (!investigationId) {
    throw new Error(
      "Investigation ID is required."
    );
  }

  return apiFetch(
    `/api/investigations/${encodeURIComponent(
      investigationId
    )}/relationships`
  );
}


/* =========================================================
   INVESTIGATION WORKFLOW
   ========================================================= */

export async function prepareInvestigation(
  investigationId
) {
  const [
    investigation,
    evidence,
  ] = await Promise.all([
    getInvestigation(
      investigationId
    ),
    getInvestigationEvidence(
      investigationId
    ),
  ]);

  return {
    investigation,
    evidence:
      Array.isArray(evidence)
        ? evidence
        : evidence?.evidence || [],
  };
}


export async function loadInvestigationWorkspace(
  investigationId
) {
  if (!investigationId) {
    throw new Error(
      "Investigation ID is required."
    );
  }

  const [
    investigation,
    evidence,
    fragments,
    relationships,
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

  return {
    investigation,

    evidence:
      Array.isArray(evidence)
        ? evidence
        : evidence?.evidence || [],

    fragments:
      Array.isArray(fragments)
        ? fragments
        : fragments?.fragments || [],

    relationships:
      Array.isArray(relationships)
        ? relationships
        : relationships?.relationships || [],
  };
}


export async function attachMultipleEvidence(
  investigationId,
  evidenceIds
) {
  const ids = [
    ...new Set(
      (
        Array.isArray(evidenceIds)
          ? evidenceIds
          : []
      ).filter(Boolean)
    ),
  ];

  const results = [];

  for (const evidenceId of ids) {
    results.push(
      await attachEvidenceToInvestigation(
        investigationId,
        evidenceId
      )
    );
  }

  return results;
}


export async function runInvestigationAnalysis(
  investigationId
) {
  const analysis =
    await analyzeInvestigation(
      investigationId
    );

  let relationships = null;

  try {
    relationships =
      await analyzeInvestigationRelationships(
        investigationId
      );
  } catch (error) {
    console.warn(
      "Investigation relationship analysis failed:",
      error
    );
  }

  return {
    investigationId,
    analysis,
    relationships,
  };
}


export async function analyzeAndLoadInvestigation(
  investigationId
) {
  await analyzeInvestigation(
    investigationId
  );

  try {
    await analyzeInvestigationRelationships(
      investigationId
    );
  } catch (error) {
    console.warn(
      "Relationship analysis could not be completed:",
      error
    );
  }

  return loadInvestigationWorkspace(
    investigationId
  );
}


export async function getInvestigationSummary(
  investigationId
) {
  const workspace =
    await loadInvestigationWorkspace(
      investigationId
    );

  return {
    investigationId,

    investigation:
      workspace.investigation,

    evidenceCount:
      workspace.evidence.length,

    fragmentCount:
      workspace.fragments.length,

    relationshipCount:
      workspace.relationships.length,

    evidence:
      workspace.evidence,

    fragments:
      workspace.fragments,

    relationships:
      workspace.relationships,
  };
}


/* =========================================================
   ANALYSIS
   ========================================================= */

export function scanEvidence(
  evidenceId
) {
  return apiFetch(
    `/api/analysis/scan/${encodeURIComponent(
      evidenceId
    )}`
  );
}


export function getFragments(
  evidenceId
) {
  return apiFetch(
    `/api/analysis/fragments/${encodeURIComponent(
      evidenceId
    )}`
  );
}


export function analyzeRelationships(
  evidenceId
) {
  return apiFetch(
    `/api/analysis/relationships/${encodeURIComponent(
      evidenceId
    )}`,
    {
      method: "POST",
    }
  );
}


export function getRelationships(
  evidenceId
) {
  return apiFetch(
    `/api/analysis/relationships/${encodeURIComponent(
      evidenceId
    )}`
  );
}


/* =========================================================
   RECONSTRUCTION
   ========================================================= */

export function runReconstruction(
  evidenceId
) {
  return apiFetch(
    `/api/reconstruction/run/${encodeURIComponent(
      evidenceId
    )}`,
    {
      method: "POST",
    }
  );
}


export function getReconstructionResults(
  evidenceId
) {
  return apiFetch(
    `/api/reconstruction/results/${encodeURIComponent(
      evidenceId
    )}`
  );
}


export function getReconstructionAssessment(
  reconstructionId
) {
  return apiFetch(
    `/api/reconstruction/${encodeURIComponent(
      reconstructionId
    )}/assessment`
  );
}


export function getReconstructionContributions(
  reconstructionId
) {
  return apiFetch(
    `/api/reconstruction/${encodeURIComponent(
      reconstructionId
    )}/contributions`
  );
}


export function getReconstructionEvidenceAnalysis(
  reconstructionId
) {
  return apiFetch(
    `/api/reconstruction/${encodeURIComponent(
      reconstructionId
    )}/evidence-analysis`
  );
}


export function getReconstructionPriority(
  reconstructionId
) {
  return apiFetch(
    `/api/reconstruction/${encodeURIComponent(
      reconstructionId
    )}/priority`
  );
}


export function getReconstructionDna(
  reconstructionId
) {
  return apiFetch(
    `/api/reconstruction/${encodeURIComponent(
      reconstructionId
    )}/dna`
  );
}


export function getReconstructionProvenance(
  reconstructionId
) {
  return apiFetch(
    `/api/reconstruction/${encodeURIComponent(
      reconstructionId
    )}/provenance`
  );
}


/* =========================================================
   RECOVERED ARTIFACT PREVIEW / DOWNLOAD
   ========================================================= */

export function getReconstructionPreviewUrl(
  reconstructionId
) {
  if (!reconstructionId) {
    throw new Error(
      "Reconstruction ID is required."
    );
  }

  return (
    `${API_BASE_URL}` +
    `/api/reconstruction/${encodeURIComponent(
      reconstructionId
    )}/preview`
  );
}


export function getReconstructionDownloadUrl(
  reconstructionId
) {
  if (!reconstructionId) {
    throw new Error(
      "Reconstruction ID is required."
    );
  }

  return (
    `${API_BASE_URL}` +
    `/api/reconstruction/${encodeURIComponent(
      reconstructionId
    )}/download`
  );
}


/* =========================================================
   ORIGINAL EVIDENCE PREVIEW / DOWNLOAD
   ========================================================= */

export function getEvidencePreviewUrl(
  evidenceId
) {
  if (!evidenceId) {
    throw new Error(
      "Evidence ID is required."
    );
  }

  return (
    `${API_BASE_URL}` +
    `/api/evidence/${encodeURIComponent(
      evidenceId
    )}/preview`
  );
}


export function getEvidenceDownloadUrl(
  evidenceId
) {
  if (!evidenceId) {
    throw new Error(
      "Evidence ID is required."
    );
  }

  return (
    `${API_BASE_URL}` +
    `/api/evidence/${encodeURIComponent(
      evidenceId
    )}/download`
  );
}


export function getEvidenceRegions(
  evidenceId
) {
  return apiFetch(
    `/api/evidence/${encodeURIComponent(
      evidenceId
    )}/regions`
  );
}


/* =========================================================
   RECOVERY COMPARISON
   ========================================================= */

export function getRecoveryComparison(
  evidenceId,
  reconstructionId
) {
  const params =
    reconstructionId
      ? `?reconstruction_id=${encodeURIComponent(
          reconstructionId
        )}`
      : "";

  return apiFetch(
    `/api/recovery-comparison/${encodeURIComponent(
      evidenceId
    )}${params}`
  );
}


/* =========================================================
   EVIDENCE QUERY
   ========================================================= */

export function askEvidenceQuery(
  evidenceId,
  question
) {
  return apiFetch(
    `/api/evidence/${encodeURIComponent(
      evidenceId
    )}/query?question=${encodeURIComponent(
      question
    )}`
  );
}


/* =========================================================
   EVIDENCE COPILOT + OLLAMA
   ========================================================= */

export function askCopilotQuestion(
  evidenceId,
  question,
  options = {}
) {
  if (!evidenceId) {
    throw new Error(
      "Evidence ID is required."
    );
  }

  if (!question?.trim()) {
    throw new Error(
      "Question is required."
    );
  }

  const useOllama =
    options.useOllama !== false;

  return apiFetch(
    "/api/copilot/query",
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
      },

      body: JSON.stringify({
        evidence_id:
          evidenceId,

        question:
          question.trim(),

        use_ollama:
          useOllama,
      }),
    }
  );
}