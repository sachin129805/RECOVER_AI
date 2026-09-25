import React, {

  useEffect,

  useMemo,

  useState,

} from "react";



import {

  Eye,

  Download,

  GitBranch,

  ScanLine,

  ShieldCheck,

  Bot,

  RefreshCw,

  AlertTriangle,

} from "lucide-react";



import Card from "../components/common/Card";

import Badge from "../components/common/Badge";

import EvidenceCopilot from "../components/evidence/EvidenceCopilot";



import {

  getInvestigation,

  getInvestigationEvidence,

  scanEvidence,

  getReconstructionResults,

  getRecoveryComparison,

  getReconstructionAssessment,

  getReconstructionPriority,

  getReconstructionDna,

  getReconstructionProvenance,

  getEvidencePreviewUrl,

  getEvidenceDownloadUrl,

  getReconstructionPreviewUrl,

  getReconstructionDownloadUrl,

  getEvidenceRegions,

} from "../api";





const tone = (

  status = ""

) => {



  if (

    status.includes(

      "Verified"

    )

  ) {

    return "success";

  }



  if (

    status.includes(

      "Insufficient"

    )

  ) {

    return "danger";

  }



  if (

    status.includes(

      "AI-Inferred"

    ) ||

    status.includes(

      "Inferred"

    )

  ) {

    return "warning";

  }



  if (

    status.includes(

      "Corrupted"

    ) ||

    status.includes(

      "Incomplete"

    )

  ) {

    return "warning";

  }



  return "info";

};





const priorityTone = (

  priority = ""

) => {



  const value =

    String(

      priority

    ).toLowerCase();



  if (

    value === "high"

  ) {

    return "danger";

  }



  if (

    value === "medium"

  ) {

    return "warning";

  }



  return "info";

};





const formatBytes = (

  value

) => {



  if (

    value === null ||

    value === undefined ||

    Number.isNaN(

      Number(value)

    )

  ) {

    return "Not available";

  }



  const bytes =

    Number(value);



  if (

    bytes >=

    1024 *

    1024 *

    1024

  ) {

    return `${(

      bytes /

      (1024 *

        1024 *

        1024)

    ).toFixed(2)} GB`;

  }



  if (

    bytes >=

    1024 *

    1024

  ) {

    return `${(

      bytes /

      (1024 *

        1024)

    ).toFixed(2)} MB`;

  }



  if (

    bytes >=

    1024

  ) {

    return `${(

      bytes /

      1024

    ).toFixed(2)} KB`;

  }



  return `${bytes} B`;

};





const formatPercent = (

  value

) => {



  if (

    value === null ||

    value === undefined ||

    Number.isNaN(

      Number(value)

    )

  ) {

    return "Not available";

  }



  return `${Number(

    value

  ).toFixed(

    Number(value) % 1 ===

      0

      ? 0

      : 1

  )}%`;

};





const asList = (

  value,

  key

) => {



  if (

    Array.isArray(

      value

    )

  ) {

    return value;

  }



  if (

    Array.isArray(

      value?.[key]

    )

  ) {

    return value[key];

  }



  return [];

};





export default function RecoveredEvidence() {



  const [

    investigation,

    setInvestigation,

  ] = useState(null);



  const [

    evidenceItems,

    setEvidenceItems,

  ] = useState([]);



  const [

    evidence,

    setEvidence,

  ] = useState(null);



  const [

    analysis,

    setAnalysis,

  ] = useState(null);



  const [

    reconstructions,

    setReconstructions,

  ] = useState([]);



  const [

    assessment,

    setAssessment,

  ] = useState(null);



  const [

    priority,

    setPriority,

  ] = useState(null);



  const [

    dna,

    setDna,

  ] = useState(null);



  const [

    provenance,

    setProvenance,

  ] = useState(null);



  const [

    comparisonResults,

    setComparisonResults,

  ] = useState([]);



  const [

    active,

    setActive,

  ] = useState(null);



  const [

    pos,

    setPos,

  ] = useState(52);



  const [

    copilotOpen,

    setCopilotOpen,

  ] = useState(true);



  const [

    loading,

    setLoading,

  ] = useState(true);



  const [

    refreshing,

    setRefreshing,

  ] = useState(false);



  const [

    error,

    setError,

  ] = useState("");



  const [

    previewOpen,

    setPreviewOpen,

  ] = useState(false);



  const [

    previewUrl,

    setPreviewUrl,

  ] = useState("");



  const [

    previewTitle,

    setPreviewTitle,

  ] = useState("");



  const [

    damageOpen,

    setDamageOpen,

  ] = useState(false);



  const [

    damageRegions,

    setDamageRegions,

  ] = useState([]);



  const [

    damageLoading,

    setDamageLoading,

  ] = useState(false);





  const investigationId =

    localStorage.getItem(

      "recoverai_investigation_id"

    ) || null;





  const loadReconstructionDetails =

    async (

      evidenceId,

      reconstructionList

    ) => {



      const latest =

        reconstructionList?.[0];



      if (

        !latest?.reconstruction_id

      ) {



        setAssessment(null);

        setPriority(null);

        setDna(null);

        setProvenance(null);



        return;

      }





      const reconstructionId =

        latest.reconstruction_id;





      const results =

        await Promise.allSettled([

          getReconstructionAssessment(

            reconstructionId

          ),



          getReconstructionPriority(

            reconstructionId

          ),



          getReconstructionDna(

            reconstructionId

          ),



          getReconstructionProvenance(

            reconstructionId

          ),

        ]);





      const value =

        (result) =>

          result.status ===

          "fulfilled"

            ? result.value

            : null;





      setAssessment(

        value(results[0])

      );



      setPriority(

        value(results[1])

      );



      setDna(

        value(results[2])

      );



      setProvenance(

        value(results[3])

      );

    };





  const loadEvidence =

    async (

      item

    ) => {



      if (

        !item?.evidence_id

      ) {

        return;

      }





      const evidenceId =

        item.evidence_id;





      const [

        scanResult,

        reconstructionResult,

        comparisonResult,

      ] =

        await Promise.all([

          scanEvidence(

            evidenceId

          ),



          getReconstructionResults(

            evidenceId

          ),



          getRecoveryComparison(

            evidenceId

          ),

        ]);





      const reconstructionList =

        asList(

          reconstructionResult,

          "results"

        );





      const comparisonList =

        asList(

          comparisonResult,

          "results"

        );





      setEvidence(

        item

      );



      setAnalysis(

        scanResult

      );



      setReconstructions(

        reconstructionList

      );



      setComparisonResults(

        comparisonList

      );





      await loadReconstructionDetails(

        evidenceId,

        reconstructionList

      );





      localStorage.setItem(

        "recoverai_current_evidence",

        JSON.stringify(

          item

        )

      );





      localStorage.setItem(

        "recoverai_analysis_result",

        JSON.stringify(

          scanResult

        )

      );





      localStorage.setItem(

        "recoverai_reconstruction_result",

        JSON.stringify(

          reconstructionList

        )

      );

    };





  const loadWorkspace =

    async () => {



      setLoading(true);

      setError("");





      try {



        let items = [];





        if (

          investigationId

        ) {



          const [

            investigationResult,

            evidenceResult,

          ] =

            await Promise.all([

              getInvestigation(

                investigationId

              ),



              getInvestigationEvidence(

                investigationId

              ),

            ]);





          setInvestigation(

            investigationResult

          );





          items =

            asList(

              evidenceResult,

              "evidence"

            );

        }





        if (

          !items.length

        ) {



          const storedEvidence =

            localStorage.getItem(

              "recoverai_current_evidence"

            );





          if (

            storedEvidence

          ) {



            try {



              const parsed =

                JSON.parse(

                  storedEvidence

                );



              items =

                parsed

                  ? [parsed]

                  : [];



            } catch {



              items = [];

            }

          }

        }





        setEvidenceItems(

          items

        );





        if (

          !items.length

        ) {



          setEvidence(null);

          setActive(null);

          setAnalysis(null);

          setReconstructions([]);

          setComparisonResults([]);



          return;

        }





        let current =

          null;





        try {



          const stored =

            localStorage.getItem(

              "recoverai_current_evidence"

            );





          if (

            stored

          ) {



            const parsed =

              JSON.parse(

                stored

              );





            current =

              items.find(

                (item) =>

                  item.evidence_id ===

                  parsed?.evidence_id

              ) ||

              null;

          }



        } catch {



          current = null;

        }





        current =

          current ||

          items[0];





        setActive({

          id:

            current.evidence_id,



          name:

            current.filename,



          type:

            current.file_type ||

            current.extension ||

            "Unknown",



          status:

            current.upload_status ||

            "Stored",



          evidence_id:

            current.evidence_id,



          size_bytes:

            current.size_bytes,



          sha256:

            current.sha256,



          metadata:

            current.metadata,

        });





        await loadEvidence(

          current

        );



      } catch (

        err

      ) {



        console.error(

          "Failed to load recovered evidence:",

          err

        );





        setError(

          err.message ||

          "Unable to load recovered evidence."

        );



      } finally {



        setLoading(

          false

        );

      }

    };





  useEffect(

    () => {

      loadWorkspace();

    },

    [investigationId]

  );





  const refresh =

    async () => {



      setRefreshing(

        true

      );



      setError("");





      try {



        await loadWorkspace();



      } finally {



        setRefreshing(

          false

        );

      }

    };





  const selectEvidence =

    async (

      item

    ) => {



      setError("");





      const viewModel = {



        id:

          item.evidence_id,



        name:

          item.filename,



        type:

          item.file_type ||

          item.extension ||

          "Unknown",



        status:

          item.upload_status ||

          "Stored",



        evidence_id:

          item.evidence_id,



        size_bytes:

          item.size_bytes,



        sha256:

          item.sha256,



        metadata:

          item.metadata,

      };





      setActive(

        viewModel

      );





      try {



        setLoading(

          true

        );



        await loadEvidence(

          item

        );



      } catch (

        err

      ) {



        setError(

          err.message ||

          "Unable to load selected evidence."

        );



      } finally {



        setLoading(

          false

        );

      }

    };





  const latestReconstruction =

    reconstructions[0] ||

    {};





  const openOriginalPreview =

    () => {



      if (

        !active?.evidence_id

      ) {

        return;

      }





      setPreviewTitle(

        active.name ||

        "Evidence preview"

      );





      setPreviewUrl(

        getEvidencePreviewUrl(

          active.evidence_id

        )

      );





      setPreviewOpen(

        true

      );

    };





  const downloadOriginal =

    () => {



      if (

        !active?.evidence_id

      ) {

        return;

      }





      window.open(

        getEvidenceDownloadUrl(

          active.evidence_id

        ),

        "_blank",

        "noopener,noreferrer"

      );

    };





  const openReconstructionPreview =

    () => {



      if (

        !latestReconstruction?.reconstruction_id

      ) {



        setError(

          "No reconstructed artifact is currently available for preview."

        );



        return;

      }





      setPreviewTitle(

        latestReconstruction.output_filename ||

        "Recovered artifact"

      );





      setPreviewUrl(

        getReconstructionPreviewUrl(

          latestReconstruction.reconstruction_id

        )

      );





      setPreviewOpen(

        true

      );

    };





  const downloadReconstruction =

    () => {



      if (

        !latestReconstruction?.reconstruction_id

      ) {



        setError(

          "No reconstructed artifact is currently available for download."

        );



        return;

      }





      window.open(

        getReconstructionDownloadUrl(

          latestReconstruction.reconstruction_id

        ),

        "_blank",

        "noopener,noreferrer"

      );

    };





  const openDamageMap =

    async () => {



      if (

        !active?.evidence_id

      ) {

        return;

      }





      setDamageLoading(

        true

      );



      setDamageOpen(

        true

      );



      setError("");





      try {



        const result =

          await getEvidenceRegions(

            active.evidence_id

          );





        setDamageRegions(

          asList(

            result,

            "regions"

          )

        );



      } catch (

        err

      ) {



        setDamageRegions([]);



        setError(

          err.message ||

          "Unable to load evidence damage regions."

        );



      } finally {



        setDamageLoading(

          false

        );

      }

    };





  const exportEvidencePackage =

    () => {



      const payload = {



        exported_at:

          new Date().toISOString(),



        evidence:

          evidence,



        analysis:

          analysis,



        reconstruction:

          latestReconstruction,



        comparison:

          comparisonResults,



        assessment:

          assessment,



        priority:

          priority,



        dna:

          dna,



        provenance:

          provenance,

      };





      const blob =

        new Blob(

          [

            JSON.stringify(

              payload,

              null,

              2

            ),

          ],

          {

            type:

              "application/json",

          }

        );





      const url =

        URL.createObjectURL(

          blob

        );





      const anchor =

        document.createElement(

          "a"

        );





      anchor.href =

        url;





      anchor.download =

        `${

          active?.name ||

          "recoverai-evidence"

        }.recoverai.json`;





      document.body.appendChild(

        anchor

      );





      anchor.click();





      anchor.remove();





      URL.revokeObjectURL(

        url

      );

    };





  const comparisonSummary =

    useMemo(

      () => {



        const latest =

          comparisonResults[0] ||

          {};





        return {



          original:

            latest.source_size_bytes ??

            latest.original_size_bytes ??

            null,



          recovered:

            latest.recovered_size_bytes ??

            latest.reconstructed_size_bytes ??

            null,



          verified:

            latest.verified_bytes ??

            null,



          missing:

            latest.missing_bytes ??

            null,



          status:

            latest.comparison_status ||

            "NO_REFERENCE_AVAILABLE",



          referenceAvailable:

            latest.reference_available ??

            false,

        };



      },

      [

        comparisonResults,

      ]

    );





  const files =

    useMemo(

      () => {



        const fragments =

          analysis?.results?.flatMap(

            (

              result

            ) =>

              result.detections ||

              []

          ) || [];





        if (

          fragments.length

        ) {



          return fragments.map(

            (

              fragment,

              index

            ) => {



              const confidence =

                fragment.classification_confidence ??

                fragment.confidence ??

                0;





              return {



                id:

                  fragment.fragment_id ||

                  `FR-${index + 1}`,



                name:

                  fragment.filename ||

                  evidence?.filename ||

                  `fragment-${index + 1}`,



                type:

                  fragment.file_type ||

                  evidence?.file_type ||

                  "Unknown",



                status:

                  fragment.recovery_status ||

                  "Candidate",



                integrity:

                  typeof fragment.structural_integrity ===

                  "number"

                    ? `${fragment.structural_integrity}%`

                    : "—",



                confidence:



                  confidence,



                priority:

                  fragment.priority ||

                  (

                    confidence >= 80

                      ? "High"

                      : confidence >= 50

                        ? "Medium"

                        : "Low"

                  ),



                fragments:

                  1,

              };

            }

          );

        }





        if (

          !evidence

        ) {

          return [];

        }





        return [

          {



            id:

              evidence.evidence_id,



            name:

              evidence.filename,



            type:

              evidence.file_type ||

              evidence.extension ||

              "Unknown",



            status:

              latestReconstruction.status ||

              "Candidate",



            integrity:

              latestReconstruction.structural_integrity !=

              null

                ? `${latestReconstruction.structural_integrity}%`

                : "—",



            confidence:

              latestReconstruction.recovery_confidence ??

              0,



            priority:

              latestReconstruction.priority ||

              "Medium",



            fragments:

              latestReconstruction.fragments_used

                ?.length ||

              analysis?.fragment_count ||

              0,

          },

        ];



      },

      [

        analysis,

        evidence,

        latestReconstruction,

      ]

    );





  useEffect(

    () => {



      if (

        !active &&

        files.length

      ) {



        setActive(

          files[0]

        );

      }



    },

    [

      active,

      files,

    ]

  );





  const recoverySummary =

    useMemo(

      () => {



        const latest =

          reconstructions[0] ||

          {};





        const verified =

          Number(

            latest.verified_bytes ||

            0

          );





        const missing =

          Number(

            latest.missing_bytes ||

            0

          );





        const reconstructed =

          Number(

            latest.reconstructed_size ??

            latest.recovered_size_bytes ??

            0

          );





        const total =

          verified +

            missing ||

          reconstructed ||

          Number(

            evidence?.size_bytes ||

            0

          ) ||

          1;





        const completeness =

          Math.min(

            100,

            Math.round(

              (

                verified /

                total

              ) *

              100

            ) || 0

          );





        return {



          completeness,



          structural:

            latest.structural_integrity ??

            assessment?.structural_integrity ??

            null,



          confidence:

            latest.recovery_confidence ??

            assessment?.recovery_confidence ??

            null,



          verified,



          reconstructed,



          missing,



          status:

            latest.status ||

            assessment?.status ||

            "No reconstruction result",

        };



      },

      [

        reconstructions,

        assessment,

        evidence,

      ]

    );





  const priorityValue =

    priority?.priority ||

    priority?.level ||

    latestReconstruction.priority ||

    "Not available";





  const dnaHash =

    dna?.sha256 ||

    dna?.hash ||

    evidence?.sha256 ||

    null;





  const dnaFragmentCount =

    dna?.fragment_count ??

    latestReconstruction.fragments_used

      ?.length ??

    analysis?.fragment_count ??

    0;





  const provenanceSteps =

    useMemo(

      () => {



        const steps =

          provenance?.steps ||

          provenance?.events ||

          provenance?.provenance ||

          null;





        if (

          Array.isArray(

            steps

          )

        ) {

          return steps;

        }





        return [

          "Original Evidence",

          "Storage Block",

          "Fragment",

          "Reconstruction",

          "Validation",

          "Confidence",

          "Final Evidence",

        ];



      },

      [

        provenance,

      ]

    );





  if (

    loading &&

    !active

  ) {



    return (

      <div className="page-intro">



        <div>



          <span className="eyebrow">

            EVIDENCE LIBRARY

          </span>



          <h2>

            Recovered Evidence

          </h2>



          <p>

            Loading live recovery results...

          </p>



        </div>



        <Badge tone="info">

          LOADING

        </Badge>



      </div>

    );

  }





  if (

    !active

  ) {



    return (

      <div className="page-intro">



        <div>



          <span className="eyebrow">

            EVIDENCE LIBRARY

          </span>



          <h2>

            Recovered Evidence

          </h2>



          <p>

            Waiting for evidence to be uploaded

            and analyzed.

          </p>



        </div>



      </div>

    );

  }





  return (

    <div className="recovered-evidence-page">



      <div className="page-intro">



        <div>



          <span className="eyebrow">

            EVIDENCE LIBRARY

          </span>



          <h2>

            Recovered Evidence

          </h2>



          <p>

            Review recovery results,

            uncertainty, provenance and

            comparison data from the live

            forensic backend.

          </p>



        </div>





        <div className="toolbar">



          <button

            className="secondary-btn"

            onClick={refresh}

            disabled={refreshing}

            type="button"

          >



            <RefreshCw

              size={16}

              className={

                refreshing

                  ? "spin"

                  : ""

              }

            />



            Refresh



          </button>





          <button

            className="secondary-btn"

            type="button"

            onClick={openDamageMap}

          >



            <ScanLine size={16} />



            Damage Map



          </button>





          <button

            className="secondary-btn"

            type="button"

            onClick={

              exportEvidencePackage

            }

          >



            <Download size={16} />



            Export



          </button>





          {!copilotOpen && (



            <button

              className="secondary-btn copilot-open-btn"

              onClick={() =>

                setCopilotOpen(

                  true

                )

              }

              type="button"

            >



              <Bot size={16} />



              Evidence AI



            </button>



          )}



        </div>



      </div>





      {error && (



        <Card>



          <div className="contradiction">



            <AlertTriangle size={18} />



            <div>



              <b>

                Evidence Loading Error

              </b>



              <p>

                {error}

              </p>



            </div>



          </div>



        </Card>



      )}





      <div

        className={

          copilotOpen

            ? "evidence-workspace with-copilot"

            : "evidence-workspace"

        }

      >



        <main className="evidence-main">



          <Card className="table-card">



            <div className="filters">



              <input

                placeholder="Search evidence..."

                onChange={() => {}}

              />





              <select

                defaultValue="All statuses"

              >



                <option>

                  All statuses

                </option>



                <option>

                  Verified Recovery

                </option>



                <option>

                  Structural Repair

                </option>



                <option>

                  Plausible Reconstruction

                </option>



                <option>

                  AI-Inferred Reconstruction

                </option>



                <option>

                  Insufficient Evidence

                </option>



              </select>





              <select

                defaultValue="All types"

              >



                <option>

                  All types

                </option>



                {[

                  ...new Set(

                    files.map(

                      (item) =>

                        item.type

                    )

                  ),

                ].map(

                  (type) => (



                    <option

                      key={type}

                      value={type}

                    >

                      {type}

                    </option>



                  )

                )}



              </select>



            </div>





            <table>



              <thead>



                <tr>



                  <th>

                    Evidence

                  </th>



                  <th>

                    Type

                  </th>



                  <th>

                    Recovery

                  </th>



                  <th>

                    Integrity

                  </th>



                  <th>

                    Confidence

                  </th>



                  <th>

                    Priority

                  </th>



                  <th>

                    Actions

                  </th>



                </tr>



              </thead>





              <tbody>



                {files.map(

                  (file) => (



                    <tr

                      className={

                        active?.id ===

                        file.id

                          ? "selected-row"

                          : ""

                      }

                      key={file.id}

                      onClick={() => {



                        const original =

                          evidenceItems.find(

                            (item) =>

                              item.evidence_id ===

                              file.id

                          );





                        if (

                          original

                        ) {



                          selectEvidence(

                            original

                          );



                        } else {



                          setActive(

                            file

                          );

                        }



                      }}

                    >



                      <td>



                        <b>

                          {file.name}

                        </b>



                        <small>

                          {file.id}

                        </small>



                      </td>





                      <td>

                        {file.type}

                      </td>





                      <td>



                        <Badge

                          tone={tone(

                            file.status

                          )}

                        >

                          {file.status}

                        </Badge>



                      </td>





                      <td>

                        {file.integrity}

                      </td>





                      <td>

                        {formatPercent(

                          file.confidence

                        )}

                      </td>





                      <td>



                        <Badge

                          tone={priorityTone(

                            file.priority

                          )}

                        >

                          {file.priority}

                        </Badge>



                      </td>





                      <td>



                        <button

                          className="table-action"

                          title="Preview evidence"

                          type="button"

                          onClick={(

                            event

                          ) => {



                            event.stopPropagation();





                            const original =

                              evidenceItems.find(

                                (item) =>

                                  item.evidence_id ===

                                  file.id

                              );





                            if (

                              original

                            ) {



                              setActive({

                                id:

                                  original.evidence_id,



                                name:

                                  original.filename,



                                type:

                                  original.file_type ||

                                  original.extension ||

                                  "Unknown",



                                status:

                                  original.upload_status ||

                                  "Stored",



                                evidence_id:

                                  original.evidence_id,



                                size_bytes:

                                  original.size_bytes,



                                sha256:

                                  original.sha256,

                              });





                              setPreviewTitle(

                                original.filename

                              );





                              setPreviewUrl(

                                getEvidencePreviewUrl(

                                  original.evidence_id

                                )

                              );





                              setPreviewOpen(

                                true

                              );



                            } else {



                              openOriginalPreview();

                            }



                          }}

                        >



                          <Eye

                            size={15}

                          />



                        </button>





                        <button

                          className="table-action"

                          title="Download evidence"

                          type="button"

                          onClick={(

                            event

                          ) => {



                            event.stopPropagation();





                            const original =

                              evidenceItems.find(

                                (item) =>

                                  item.evidence_id ===

                                  file.id

                              );





                            if (

                              original

                            ) {



                              window.open(

                                getEvidenceDownloadUrl(

                                  original.evidence_id

                                ),

                                "_blank",

                                "noopener,noreferrer"

                              );



                            }



                          }}

                        >



                          <Download

                            size={15}

                          />



                        </button>



                      </td>



                    </tr>



                  )

                )}



              </tbody>



            </table>





            {!files.length && (



              <div

                style={{

                  padding:

                    "28px",



                  textAlign:

                    "center",

                }}

              >



                <p className="muted">

                  No recovered evidence

                  candidates are currently

                  available.

                </p>



              </div>



            )}



          </Card>





          <div className="evidence-detail-grid">



            <Card>



              <div className="card-title">



                <span>

                  Recovery Comparison

                </span>



                <Badge tone="info">

                  LIVE EVIDENCE

                </Badge>



              </div>





              <div className="comparison">



                <div className="compare-pane corrupted">



                  <div className="compare-label">

                    CORRUPTED INPUT

                  </div>





                 <div

                  className="fake-image damage"

                  style={{

                  position: "relative",

                  overflow: "hidden",

                  width: "100%",

                  height: "100%",

                  display: "flex",

                  alignItems: "center",

                  justifyContent: "center",

                        }}

                 >



                    {active?.evidence_id ? (



                  <img

                    src={getEvidencePreviewUrl(active.evidence_id)}

                    alt={active.name || "Evidence"}

                    style={{

                    width: "100%",

                    height: "100%",

                    objectFit: "contain",

                    objectPosition: "center",

                    display: "block",

                    background: "#f1f5f9",

                  }}

                />



                    ) : (



                      <span>

                        Evidence unavailable

                      </span>



                    )}



                  </div>



                </div>





                <div className="compare-pane recovered">



                  <div className="compare-label">

                    RECOVERED OUTPUT

                  </div>





                  <div

                    className="fake-image recovered-img"

                    style={{

                      position:

                        "relative",



                      overflow:

                        "hidden",

                    }}

                  >



                    {latestReconstruction?.reconstruction_id ? (

                       <img

                        src={getReconstructionPreviewUrl(

                        latestReconstruction.reconstruction_id

                       )}

                       alt={

                        latestReconstruction.output_filename ||

                        "Recovered artifact"

                    }

                    style={{

                      width: "100%",

                      height: "100%",

                      objectFit: "contain",

                      objectPosition: "center",

                      display: "block",

                      background: "#f1f5f9",

                    }}

                  />



                    ) : (



                      <div

                        style={{

                          height:

                            "100%",



                          display:

                            "grid",



                          placeItems:

                            "center",



                          padding:

                            20,



                          textAlign:

                            "center",

                        }}

                      >



                        <div>



                          <strong>

                            No recovered artifact

                          </strong>



                          <p

                            style={{

                              marginTop:

                                8,



                              fontSize:

                                11,



                              opacity:

                                0.65,

                            }}

                          >

                            Reconstruction requires

                            compatible fragment

                            candidates. No recovered

                            artifact is being fabricated.

                          </p>



                        </div>



                      </div>



                    )}



                  </div>



                </div>





                <div

                  className="slider-line"

                  style={{

                    left:

                      `${pos}%`,

                  }}

                />





                <input

                  className="compare-slider"

                  type="range"

                  min="10"

                  max="90"

                  value={pos}

                  onChange={(

                    event

                  ) =>

                    setPos(

                      Number(

                        event.target.value

                      )

                    )

                  }

                />



              </div>





              <div className="comparison-stats">



                <span>



                  Original{" "}



                  <b>



                    {comparisonSummary.original !==

                    null

                      ? formatBytes(

                          comparisonSummary.original

                        )

                      : formatBytes(

                          active?.size_bytes

                        )}



                  </b>



                </span>





                <span>



                  Verified{" "}



                  <b>



                    {comparisonSummary.verified !==

                    null

                      ? formatBytes(

                          comparisonSummary.verified

                        )

                      : formatBytes(

                          recoverySummary.verified

                        )}



                  </b>



                </span>





                <span>



                  Reconstructed{" "}



                  <b>



                    {comparisonSummary.recovered !==

                    null

                      ? formatBytes(

                          comparisonSummary.recovered

                        )

                      : latestReconstruction?.recovered_size_bytes !=

                        null

                        ? formatBytes(

                            latestReconstruction.recovered_size_bytes

                          )

                        : "Not available"}



                  </b>



                </span>





                <span>



                  Missing{" "}



                  <b>



                    {comparisonSummary.missing !==

                    null

                      ? formatBytes(

                          comparisonSummary.missing

                        )

                      : latestReconstruction?.missing_bytes !=

                        null

                        ? formatBytes(

                            latestReconstruction.missing_bytes

                          )

                        : "Not available"}



                  </b>



                </span>



              </div>





              <div

                style={{

                  marginTop:

                    "12px",



                  fontSize:

                    "11px",



                  color:

                    "#64748b",

                }}

              >



                Comparison status:{" "}



                <strong>

                  {

                    comparisonSummary.status

                  }

                </strong>



              </div>





              <div

                style={{

                  display:

                    "flex",



                  gap:

                    8,



                  marginTop:

                    14,



                  flexWrap:

                    "wrap",

                }}

              >



                <button

                  className="secondary-btn"

                  type="button"

                  onClick={

                    openOriginalPreview

                  }

                >



                  <Eye

                    size={15}

                  />



                  Preview Original



                </button>





                <button

                  className="secondary-btn"

                  type="button"

                  onClick={

                    downloadOriginal

                  }

                >



                  <Download

                    size={15}

                  />



                  Download Original



                </button>





                <button

                  className="secondary-btn"

                  type="button"

                  onClick={

                    openReconstructionPreview

                  }

                  disabled={

                    !latestReconstruction?.reconstruction_id

                  }

                >



                  <Eye

                    size={15}

                  />



                  Preview Recovered



                </button>





                <button

                  className="secondary-btn"

                  type="button"

                  onClick={

                    downloadReconstruction

                  }

                  disabled={

                    !latestReconstruction?.reconstruction_id

                  }

                >



                  <Download

                    size={15}

                  />



                  Download Recovered



                </button>



              </div>



            </Card>





            <div className="side-stack">



              <Card>



                <div className="card-title">

                  Evidence DNA

                </div>





                <div className="dna">



                  <ShieldCheck

                    size={34}

                  />





                  <div>



                    <b>

                      {active.name}

                    </b>



                    <span>



                      {active.type}

                      {" · "}

                      {dnaFragmentCount}

                      {" fragments"}



                    </span>



                  </div>



                </div>





                <div className="hash">



                  {dnaHash

                    ? `SHA-256 · ${dnaHash}`

                    : "SHA-256 unavailable"}



                </div>





                <div className="metric-line">



                  <span>

                    Completeness

                  </span>



                  <b>



                    {recoverySummary.completeness

                      ? `${recoverySummary.completeness}%`

                      : "Not available"}



                  </b>



                </div>





                <div className="metric-line">



                  <span>

                    Structural integrity

                  </span>



                  <b>



                    {recoverySummary.structural !==

                    null

                      ? formatPercent(

                          recoverySummary.structural

                        )

                      : "Not available"}



                  </b>



                </div>





                <div className="metric-line">



                  <span>

                    Recovery confidence

                  </span>



                  <b>



                    {recoverySummary.confidence !==

                    null

                      ? formatPercent(

                          recoverySummary.confidence

                        )

                      : "Not available"}



                  </b>



                </div>





                <div className="metric-line">



                  <span>

                    Priority

                  </span>



                  <b>

                    {priorityValue}

                  </b>



                </div>



              </Card>





              <Card>



                <div className="card-title">

                  Provenance

                </div>





                <div className="provenance">



                  {provenanceSteps.map(

                    (

                      step,

                      index

                    ) => {



                      const label =

                        typeof step ===

                        "string"

                          ? step

                          : step.name ||

                            step.event ||

                            step.stage ||

                            "Evidence Event";





                      return (



                        <div

                          key={`${label}-${index}`}

                        >



                          <i />



                          {label}





                          {index <

                            provenanceSteps.length -

                              1 && (



                            <span>

                              ›

                            </span>



                          )}



                        </div>



                      );



                    }

                  )}



                </div>



              </Card>



            </div>



          </div>





          <Card>



            <div className="card-title">



              Reconstruction Assessment



            </div>





            <div className="telemetry">



              <div>



                <small>

                  Recovery status

                </small>



                <b>

                  {

                    recoverySummary.status

                  }

                </b>



              </div>





              <div>



                <small>

                  Verified bytes

                </small>



                <b>

                  {formatBytes(

                    recoverySummary.verified

                  )}

                </b>



              </div>





              <div>



                <small>

                  Reconstructed bytes

                </small>



                <b>

                  {formatBytes(

                    recoverySummary.reconstructed

                  )}

                </b>



              </div>





              <div>



                <small>

                  Missing bytes

                </small>



                <b>

                  {formatBytes(

                    recoverySummary.missing

                  )}

                </b>



              </div>



            </div>





            {latestReconstruction.status ===

              "AI-Inferred Reconstruction" && (



              <div

                className="contradiction"

                style={{

                  marginTop:

                    "14px",

                }}

              >



                <AlertTriangle

                  size={17}

                />



                <div>



                  <b>

                    INFERRED — NOT VERIFIED

                    ORIGINAL DATA

                  </b>



                  <p>

                    This reconstruction contains

                    inferred content and must not

                    be represented as verified

                    original evidence.

                  </p>



                </div>



              </div>



            )}



          </Card>



        </main>





        {copilotOpen && (



          <EvidenceCopilot

            evidence={

              active

            }



            recoverySummary={

              recoverySummary

            }



            onClose={() =>

              setCopilotOpen(

                false

              )

            }

          />



        )}



      </div>





      {/* =====================================================

          PREVIEW MODAL

         ===================================================== */}



      {previewOpen && (



        <div

          onClick={() =>

            setPreviewOpen(

              false

            )

          }

          style={{

            position:

              "fixed",



            inset:

              0,



            zIndex:

              1000,



            background:

              "rgba(2,8,23,.72)",



            display:

              "grid",



            placeItems:

              "center",



            padding:

              24,

          }}

        >



          <div

            onClick={(

              event

            ) =>

              event.stopPropagation()

            }

            style={{

              width:

                "min(1000px, 94vw)",



              height:

                "min(760px, 90vh)",



              background:

                "#fff",



              borderRadius:

                12,



              overflow:

                "hidden",



              display:

                "flex",



              flexDirection:

                "column",



              boxShadow:

                "0 24px 80px rgba(0,0,0,.35)",

            }}

          >



            <div

              style={{

                display:

                  "flex",



                justifyContent:

                  "space-between",



                alignItems:

                  "center",



                padding:

                  "12px 16px",



                borderBottom:

                  "1px solid #e2e8f0",

              }}

            >



              <strong>

                {previewTitle}

              </strong>





              <div

                style={{

                  display:

                    "flex",



                  gap:

                    8,

                }}

              >



                <button

                  className="secondary-btn"

                  type="button"

                  onClick={() =>

                    window.open(

                      previewUrl,

                      "_blank",

                      "noopener,noreferrer"

                    )

                  }

                >

                  Open

                </button>





                <button

                  className="secondary-btn"

                  type="button"

                  onClick={() =>

                    setPreviewOpen(

                      false

                    )

                  }

                >

                  Close

                </button>



              </div>



            </div>





            <div

              style={{

                flex:

                  1,



                background:

                  "#f1f5f9",



                display:

                  "grid",



                placeItems:

                  "center",



                overflow:

                  "auto",

              }}

            >



              {(

                /\.(jpg|jpeg|png|gif|webp)$/i.test(

                  previewTitle

                )

              ) ? (



                <img

                  src={

                    previewUrl

                  }

                  alt={

                    previewTitle

                  }

                  style={{

                    maxWidth:

                      "100%",



                    maxHeight:

                      "100%",



                    objectFit:

                      "contain",

                  }}

                />



              ) : (



                <iframe

                  title={

                    previewTitle

                  }

                  src={

                    previewUrl

                  }

                  style={{

                    width:

                      "100%",



                    height:

                      "100%",



                    border:

                      0,

                  }}

                />



              )}



            </div>



          </div>



        </div>



      )}





      {/* =====================================================

          DAMAGE MAP

         ===================================================== */}



      {damageOpen && (



        <div

          onClick={() =>

            setDamageOpen(

              false

            )

          }

          style={{

            position:

              "fixed",



            inset:

              0,



            zIndex:

              1000,



            background:

              "rgba(2,8,23,.72)",



            display:

              "grid",



            placeItems:

              "center",



            padding:

              24,

          }}

        >



          <div

            onClick={(

              event

            ) =>

              event.stopPropagation()

            }

            style={{

              width:

                "min(850px, 94vw)",



              maxHeight:

                "85vh",



              overflow:

                "auto",



              background:

                "#fff",



              borderRadius:

                12,



              padding:

                18,

            }}

          >



            <div

              style={{

                display:

                  "flex",



                justifyContent:

                  "space-between",



                alignItems:

                  "center",



                marginBottom:

                  14,

              }}

            >



              <div>



                <strong>

                  Evidence Damage Map

                </strong>



                <div

                  style={{

                    fontSize:

                      11,



                    color:

                      "#64748b",

                  }}

                >

                  {active.name}

                </div>



              </div>





              <button

                className="secondary-btn"

                type="button"

                onClick={() =>

                  setDamageOpen(

                    false

                  )

                }

              >

                Close

              </button>



            </div>





            {damageLoading ? (



              <p className="muted">

                Loading evidence regions...

              </p>



            ) : damageRegions.length ? (



              <div

                style={{

                  display:

                    "grid",



                  gap:

                    8,

                }}

              >



                {damageRegions.map(

                  (

                    region,

                    index

                  ) => (



                    <div

                      key={

                        index

                      }

                      style={{

                        padding:

                          12,



                        border:

                          "1px solid #e2e8f0",



                        borderRadius:

                          8,



                        background:

                          "#f8fafc",

                      }}

                    >



                      <strong>

                        {

                          region.kind ||

                          region.type ||

                          "Region"

                        }

                      </strong>





                      <div

                        style={{

                          fontSize:

                            11,



                          color:

                            "#475569",



                          marginTop:

                            4,

                        }}

                      >

                        {JSON.stringify(

                          region

                        )}

                      </div>



                    </div>



                  )

                )}



              </div>



            ) : (



              <p className="muted">

                No damage regions are currently

                reported by the backend.

              </p>



            )}



          </div>



        </div>



      )}





      <style>{`



        .spin {

          animation:

            recoverai-spin

            0.9s

            linear

            infinite;

        }





        @keyframes recoverai-spin {



          from {

            transform:

              rotate(0deg);

          }



          to {

            transform:

              rotate(360deg);

          }



        }



      `}</style>



    </div>

  );

}
