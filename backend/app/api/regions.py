import json

from fastapi import APIRouter, HTTPException

from app.core.database import get_connection

router = APIRouter(prefix="/api/evidence", tags=["Evidence Regions"])


def _merge_adjacent_regions(regions):
    if not regions:
        return []
    ordered = sorted(regions, key=lambda item: (int(item["start"]), int(item["end"])))
    merged = [dict(ordered[0])]
    for region in ordered[1:]:
        previous = merged[-1]
        status_matches = previous.get("status") == region.get("status")
        same_fragment = previous.get("fragment_id") == region.get("fragment_id")
        if status_matches and (same_fragment or previous.get("fragment_id") is None or region.get("fragment_id") is None):
            previous_end = int(previous.get("end") or 0)
            current_start = int(region.get("start") or 0)
            if current_start <= previous_end + 1:
                previous["end"] = max(previous_end, int(region.get("end") or current_start))
                previous["length"] = max(0, int(previous["end"]) - int(previous["start"]))
                previous["confidence"] = previous.get("confidence") if previous.get("confidence") is not None else region.get("confidence")
                continue
        merged.append(dict(region))
    return merged


@router.get("/{evidence_id}/regions")
def get_evidence_regions(evidence_id: str):
    connection = get_connection()
    evidence = connection.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    if evidence is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Evidence not found.")

    fragments = connection.execute(
        "SELECT * FROM fragments WHERE evidence_id = ? ORDER BY offset ASC",
        (evidence_id,),
    ).fetchall()
    reconstructions = connection.execute(
        "SELECT * FROM reconstructions WHERE evidence_id = ? ORDER BY created_at DESC LIMIT 1",
        (evidence_id,),
    ).fetchone()
    connection.close()

    regions = []
    for fragment in fragments:
        start = int(fragment["offset"])
        end = start + int(fragment["sample_size"] or 0)
        regions.append({
            "start": start,
            "end": end,
            "length": max(0, end - start),
            "status": "VERIFIED" if int(fragment.get("verified_bytes") or 0) > 0 else "UNKNOWN",
            "fragment_id": fragment["fragment_id"],
            "confidence": fragment.get("classification_confidence"),
        })

    if reconstructions is not None:
        missing_regions = json.loads(reconstructions["missing_regions"] or "[]") if reconstructions.get("missing_regions") else []
        for item in missing_regions:
            start = int(item.get("start") or item.get("previous_end") or 0)
            end = int(item.get("end") or item.get("next_start") or start)
            if end < start:
                end = start
            regions.append({
                "start": start,
                "end": end,
                "length": max(0, end - start),
                "status": "MISSING",
                "fragment_id": None,
                "confidence": None,
            })

    return {"evidence_id": evidence_id, "regions": _merge_adjacent_regions(regions)[:500]}
