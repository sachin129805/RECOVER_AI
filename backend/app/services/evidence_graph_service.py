import json

from app.core.database import get_connection


MAX_GRAPH_NODES = 250
MAX_GRAPH_EDGES = 500


def _add_node(nodes, node_id: str, node_type: str, label: str, metadata: dict | None = None):
    if not node_id:
        return
    if any(node["id"] == node_id for node in nodes):
        return
    nodes.append({
        "id": str(node_id),
        "type": node_type,
        "label": str(label or node_id),
        "metadata": metadata or {},
    })


def _add_edge(edges, source: str, target: str, relation: str):
    if not source or not target:
        return
    edge = {"source": str(source), "target": str(target), "relation": relation}
    if edge in edges:
        return
    edges.append(edge)


def build_evidence_graph(evidence_id: str):
    connection = get_connection()
    evidence = connection.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    if evidence is None:
        connection.close()
        return {"nodes": [], "edges": []}

    evidence_data = dict(evidence)
    fragments = [dict(row) for row in connection.execute(
        "SELECT * FROM fragments WHERE evidence_id = ? ORDER BY offset ASC",
        (evidence_id,),
    ).fetchall()]
    relationships = [dict(row) for row in connection.execute(
        "SELECT * FROM fragment_relationships WHERE evidence_id = ? ORDER BY created_at DESC",
        (evidence_id,),
    ).fetchall()]
    reconstructions = [dict(row) for row in connection.execute(
        "SELECT * FROM reconstructions WHERE evidence_id = ? ORDER BY created_at DESC",
        (evidence_id,),
    ).fetchall()]
    provenance_rows = [dict(row) for row in connection.execute(
        "SELECT * FROM evidence_provenance WHERE evidence_id = ? ORDER BY created_at DESC",
        (evidence_id,),
    ).fetchall()]
    benchmark_rows = connection.execute("SELECT * FROM benchmark_runs WHERE evidence_id = ? ORDER BY created_at DESC LIMIT 10", (evidence_id,)).fetchall()
    connection.close()

    nodes = []
    edges = []
    evidence_node_id = evidence_data["evidence_id"]
    _add_node(nodes, evidence_node_id, "Evidence", evidence_data.get("filename") or evidence_node_id, {
        "sha256": evidence_data.get("sha256"),
        "size_bytes": evidence_data.get("size_bytes"),
    })

    for fragment in fragments[:MAX_GRAPH_NODES]:
        fragment_id = fragment.get("fragment_id")
        _add_node(nodes, fragment_id, "Fragment", fragment.get("filename") or fragment_id, {
            "offset": fragment.get("offset"),
            "sample_size": fragment.get("sample_size"),
            "integrity_status": fragment.get("integrity_status"),
        })
        _add_edge(edges, evidence_node_id, fragment_id, "CONTAINS")

    for relationship in relationships[:MAX_GRAPH_NODES]:
        relationship_id = relationship.get("relationship_id")
        _add_node(nodes, relationship_id, "Relationship", relationship.get("relationship") or relationship_id, {
            "score": relationship.get("relationship_score"),
        })
        _add_edge(edges, relationship.get("fragment_a_id"), relationship_id, "RELATED_TO")
        _add_edge(edges, relationship.get("fragment_b_id"), relationship_id, "RELATED_TO")

    for reconstruction in reconstructions[:MAX_GRAPH_NODES]:
        reconstruction_id = reconstruction.get("reconstruction_id")
        _add_node(nodes, reconstruction_id, "Reconstruction", reconstruction.get("status") or reconstruction_id, {
            "status": reconstruction.get("status"),
            "confidence": reconstruction.get("recovery_confidence"),
            "priority": reconstruction.get("priority"),
        })
        _add_edge(edges, evidence_node_id, reconstruction_id, "RECONSTRUCTED_FROM")
        for fragment_id in json.loads(reconstruction.get("fragment_ids") or "[]")[:20]:
            _add_edge(edges, fragment_id, reconstruction_id, "DERIVED_FROM")

        validation_id = f"{reconstruction_id}-validation"
        _add_node(nodes, validation_id, "Validation", reconstruction.get("status") or "validation", {
            "status": reconstruction.get("status"),
            "structural_integrity": reconstruction.get("structural_integrity"),
        })
        _add_edge(edges, reconstruction_id, validation_id, "VALIDATED_BY")

        assessment_id = f"{reconstruction_id}-assessment"
        _add_node(nodes, assessment_id, "RecoveryAssessment", reconstruction.get("priority") or "assessment", {
            "priority": reconstruction.get("priority"),
            "priority_score": reconstruction.get("priority_score"),
            "confidence": reconstruction.get("recovery_confidence"),
        })
        _add_edge(edges, reconstruction_id, assessment_id, "ASSESSED_AS")

    for provenance in provenance_rows[:MAX_GRAPH_NODES]:
        provenance_id = provenance.get("provenance_id")
        _add_node(nodes, provenance_id, "Provenance", provenance.get("recovery_status") or provenance_id, {
            "recovery_status": provenance.get("recovery_status"),
            "validation_result": provenance.get("validation_result"),
        })
        _add_edge(edges, evidence_node_id, provenance_id, "HAS_PROVENANCE")

    for benchmark in benchmark_rows:
        benchmark_id = benchmark["benchmark_id"]
        _add_node(nodes, benchmark_id, "Benchmark", benchmark_id, {
            "recovered_size": benchmark.get("recovered_size"),
            "coverage": benchmark.get("coverage"),
            "exact_sha256_match": benchmark.get("exact_sha256_match"),
        })
        _add_edge(edges, evidence_node_id, benchmark_id, "BENCHMARKED_BY")

    if len(nodes) > MAX_GRAPH_NODES:
        nodes = nodes[:MAX_GRAPH_NODES]
    if len(edges) > MAX_GRAPH_EDGES:
        edges = edges[:MAX_GRAPH_EDGES]

    return {"nodes": nodes, "edges": edges}
