import React, { useMemo } from "react";
import { Activity, Database, FileCheck2, Network, ShieldCheck, AlertTriangle, Clock3 } from "lucide-react";
import StatCard from "../components/common/StatCard";
import Card from "../components/common/Card";
import Badge from "../components/common/Badge";
import { useNavigate } from "react-router-dom";

const tone = s => s.includes("Verified") ? "success" : s.includes("Insufficient") ? "danger" : s.includes("AI") ? "warning" : "info";

export default function Dashboard(){
 const nav=useNavigate();
 const evidence = JSON.parse(localStorage.getItem("recoverai_current_evidence") || "null");
 const analysis = JSON.parse(localStorage.getItem("recoverai_analysis_result") || "null");
 const reconstructions = JSON.parse(localStorage.getItem("recoverai_reconstruction_result") || "null");
 const reconstructionList = Array.isArray(reconstructions) ? reconstructions : reconstructions ? [reconstructions] : [];

 const topEvidence = useMemo(() => {
   const rows = [];
   if (evidence) {
     rows.push({
       id: evidence.evidence_id,
       name: evidence.filename,
       type: evidence.file_type || "Unknown",
       status: reconstructionList[0]?.status || "Candidate",
       integrity: reconstructionList[0]?.structural_integrity != null ? `${reconstructionList[0].structural_integrity}%` : "—",
       confidence: reconstructionList[0]?.recovery_confidence ?? 0,
       priority: reconstructionList[0]?.priority || "Medium",
     });
   }
   if (analysis?.results?.length) {
     analysis.results.forEach((result) => {
       (result.detections || []).forEach((fragment) => {
         rows.push({
           id: fragment.fragment_id || result.filename,
           name: fragment.filename || result.filename,
           type: fragment.file_type || evidence?.file_type || "Unknown",
           status: fragment.recovery_status || "Candidate",
           integrity: typeof fragment.structural_integrity === "number" ? `${fragment.structural_integrity}%` : "—",
           confidence: fragment.classification_confidence ?? 0,
           priority: (fragment.classification_confidence ?? 0) >= 80 ? "High" : (fragment.classification_confidence ?? 0) >= 50 ? "Medium" : "Low",
         });
       });
     });
   }
   return rows.slice(0, 4);
 }, [analysis, evidence, reconstructionList]);

 const averageConfidence = useMemo(() => {
   const values = topEvidence.map((row) => Number(row.confidence || 0)).filter((value) => !Number.isNaN(value));
   if (!values.length) return 0;
   return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
 }, [topEvidence]);

 const fragmentsDetected = analysis?.fragment_count || 0;
 const recoverableFiles = reconstructionList.length || 0;
 const verifiedRecovery = reconstructionList.filter((item) => item.status === "VERIFIED_RECOVERY").length;

 return <div>
  <div className="page-intro"><div><span className="eyebrow">CURRENT INVESTIGATION</span><h2>{evidence?.filename || "Investigation"}</h2><p>{evidence ? `${evidence.file_type || "Evidence"} • analysis workspace` : "No live evidence loaded yet"}</p></div><button className="primary-btn" onClick={()=>nav("/analysis")}>Open Analysis <Activity size={16}/></button></div>
  <div className="stats-grid">
   <StatCard label="Evidence Sources" value={evidence ? 1 : 0} sub={evidence ? "Mounted source" : "Awaiting upload"} icon={Database}/>
   <StatCard label="Fragments Detected" value={fragmentsDetected.toLocaleString()} sub={fragmentsDetected ? "Current scan" : "No scan yet"} icon={Network}/>
   <StatCard label="Recoverable Files" value={recoverableFiles} sub={recoverableFiles ? "Candidate reconstruction(s)" : "Awaiting reconstruction"} icon={FileCheck2}/>
   <StatCard label="Avg. Recovery Confidence" value={`${averageConfidence}%`} sub="Across active evidence" icon={ShieldCheck}/>
  </div>
  <div className="two-col">
   <Card><div className="card-title"><span>Recovery Overview</span><Badge tone="success">ANALYSIS ACTIVE</Badge></div><div className="overview-big"><b>{verifiedRecovery || 0}</b><span>verified reconstructions</span></div><div className="bar-row"><span>Verified Recovery</span><b>{verifiedRecovery}</b></div><div className="mini-bar"><i style={{width: `${recoverableFiles ? Math.min(100, (verifiedRecovery / recoverableFiles) * 100) : 0}%`}}/></div><div className="bar-row"><span>Candidate Recovery</span><b>{Math.max(recoverableFiles - verifiedRecovery, 0)}</b></div><div className="mini-bar"><i style={{width: `${recoverableFiles ? Math.min(100, ((recoverableFiles - verifiedRecovery) / recoverableFiles) * 100) : 0}%`}}/></div></Card>
   <Card><div className="card-title"><span>AI Insights</span><span className="live-label"><i/> LIVE</span></div><div className="insight"><ShieldCheck/><div><b>{fragmentsDetected ? "Evidence scan contains active detections" : "No scan results available yet"}</b><p>{fragmentsDetected ? `${fragmentsDetected} fragments were found in the current analysis.` : "Upload evidence and start analysis to populate this panel."}</p></div></div><div className="insight"><AlertTriangle/><div><b>{reconstructionList.length ? "Reconstruction state available" : "No reconstruction yet"}</b><p>{reconstructionList.length ? `${reconstructionList.length} reconstruction result(s) are available for review.` : "Recovery assessment will appear after reconstruction runs."}</p></div></div><div className="insight"><Clock3/><div><b>Analysis progress</b><p>{analysis ? "Live backend data is available." : "Waiting for backend scan results."}</p></div></div></Card>
  </div>
  <Card className="table-card"><div className="card-title"><span>Top Priority Evidence</span><button className="text-btn" onClick={()=>nav("/evidence")}>View all</button></div><table><thead><tr><th>Evidence</th><th>Type</th><th>Status</th><th>Integrity</th><th>Confidence</th><th>Priority</th></tr></thead><tbody>{topEvidence.length ? topEvidence.map((f)=><tr key={f.id}><td><b>{f.name}</b><small>{f.id}</small></td><td>{f.type}</td><td><Badge tone={tone(f.status)}>{f.status}</Badge></td><td>{f.integrity}</td><td><b>{f.confidence}%</b></td><td><Badge tone={f.priority === "High" ? "danger" : f.priority === "Medium" ? "warning" : "info"}>{f.priority}</Badge></td></tr>) : <tr><td colSpan="6">No evidence has been uploaded yet.</td></tr>}</tbody></table></Card>
 </div>
}
