from collections import Counter


def summarize_anomalies(records):
    flags = [flag for record in records for flag in record.get("anomaly_flags", [])]
    status_counts = Counter(record.get("status", "UNKNOWN") for record in records)
    return {
        "total_records": len(records),
        "status_counts": dict(status_counts),
        "flag_counts": dict(Counter(flags)),
        "records_requiring_review": [r for r in records if r.get("status") == "REVIEW_REQUIRED"],
        "rejected_records": [r for r in records if r.get("status") == "REJECTED"],
    }
