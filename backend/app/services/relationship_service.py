import json
from uuid import uuid4

from app.core.database import get_connection
from app.ai.fragment_matcher import match_fragments


def generate_relationship_id():
    return f"REL-{uuid4().hex[:8].upper()}"


def analyze_fragment_relationships(evidence_id: str):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM fragments
        WHERE evidence_id = ?
        ORDER BY offset ASC
        """,
        (evidence_id,),
    ).fetchall()

    fragments = [dict(row) for row in rows]

    # At least two candidates are required.
    if len(fragments) < 2:
        connection.close()

        return {
            "evidence_id": evidence_id,
            "fragment_count": len(fragments),
            "relationship_count": 0,
            "status": "Insufficient fragment candidates",
            "message": (
                "At least two fragment candidates are required "
                "to evaluate a relationship."
            ),
            "relationships": [],
        }

    connection.execute(
        """
        DELETE FROM fragment_relationships
        WHERE evidence_id = ?
        """,
        (evidence_id,),
    )

    relationships = []

    for index, fragment_a in enumerate(fragments):

        for fragment_b in fragments[index + 1:]:

            result = match_fragments(
                fragment_a,
                fragment_b,
            )

            relationship_id = generate_relationship_id()
            reasons_json = json.dumps(result.get("reasons", []))

            connection.execute(
                """
                INSERT INTO fragment_relationships (
                    relationship_id,
                    evidence_id,
                    fragment_a_id,
                    fragment_b_id,
                    relationship_score,
                    relationship,
                    reasons_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship_id,
                    evidence_id,
                    fragment_a["fragment_id"],
                    fragment_b["fragment_id"],
                    result["relationship_score"],
                    result["relationship"],
                    reasons_json,
                ),
            )

            relationships.append(
                {
                    "relationship_id": relationship_id,
                    "fragment_a_id": fragment_a["fragment_id"],
                    "fragment_b_id": fragment_b["fragment_id"],
                    "relationship_score": result[
                        "relationship_score"
                    ],
                    "relationship": result["relationship"],
                    "reasons": result.get("reasons", []),
                }
            )

    connection.commit()
    connection.close()

    return {
        "evidence_id": evidence_id,
        "fragment_count": len(fragments),
        "relationship_count": len(relationships),
        "status": "Relationship analysis completed",
        "relationships": relationships,
    }


def get_fragment_relationships(evidence_id: str):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM fragment_relationships
        WHERE evidence_id = ?
        ORDER BY relationship_score DESC
        """,
        (evidence_id,),
    ).fetchall()

    connection.close()

    relationships = []

    for row in rows:
        item = dict(row)
        raw_reasons = item.get("reasons_json")

        try:
            item["reasons"] = json.loads(
                raw_reasons or "[]"
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            item["reasons"] = []

        if "reasons_json" in item:
            item.pop("reasons_json", None)

        relationships.append(item)

    return relationships