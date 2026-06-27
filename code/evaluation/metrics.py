"""Scoring functions for comparing predicted rows against the gold sample.

All functions take lists of dicts keyed by the output column names. Free-text
columns (the two justification/reason fields) are not graded for exact match.
"""

from __future__ import annotations

GRADED_COLUMNS = (
    "evidence_standard_met", "issue_type", "object_part", "claim_status",
    "supporting_image_ids", "valid_image", "severity",
)


def accuracy(pred, gold, column):
    hits = sum(1 for p, g in zip(pred, gold)
               if str(p[column]).strip() == str(g[column]).strip())
    return hits / len(gold) if gold else 0.0


def per_column_accuracy(pred, gold, columns=GRADED_COLUMNS):
    return {col: round(accuracy(pred, gold, col), 4) for col in columns}


def _labels(pred, gold, column):
    return sorted({str(r[column]).strip() for r in gold} | {str(r[column]).strip() for r in pred})


def confusion_matrix(pred, gold, column):
    labels = _labels(pred, gold, column)
    matrix = {g: {p: 0 for p in labels} for g in labels}
    for p, g in zip(pred, gold):
        matrix[str(g[column]).strip()][str(p[column]).strip()] += 1
    return labels, matrix


def macro_f1(pred, gold, column):
    labels = sorted({str(r[column]).strip() for r in gold})
    per_label = {}
    f1_values = []
    for label in labels:
        tp = sum(1 for p, g in zip(pred, gold)
                 if str(g[column]).strip() == label and str(p[column]).strip() == label)
        fp = sum(1 for p, g in zip(pred, gold)
                 if str(g[column]).strip() != label and str(p[column]).strip() == label)
        fn = sum(1 for p, g in zip(pred, gold)
                 if str(g[column]).strip() == label and str(p[column]).strip() != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_label[label] = {"precision": round(precision, 3), "recall": round(recall, 3),
                            "f1": round(f1, 3), "support": tp + fn}
        f1_values.append(f1)
    return (sum(f1_values) / len(f1_values) if f1_values else 0.0), per_label


def _flag_set(value):
    tokens = {t.strip() for t in str(value).split(";") if t.strip() and t.strip() != "none"}
    return tokens


def risk_flag_overlap(pred, gold):
    jaccard_total = 0.0
    exact = 0
    for p, g in zip(pred, gold):
        sp, sg = _flag_set(p["risk_flags"]), _flag_set(g["risk_flags"])
        if not sp and not sg:
            jaccard = 1.0
        else:
            jaccard = len(sp & sg) / len(sp | sg) if (sp | sg) else 1.0
        jaccard_total += jaccard
        if sp == sg:
            exact += 1
    n = len(gold) or 1
    return {"mean_jaccard": round(jaccard_total / n, 4), "exact_match": round(exact / n, 4)}


def evaluate(pred, gold):
    cs_f1, cs_labels = macro_f1(pred, gold, "claim_status")
    it_f1, it_labels = macro_f1(pred, gold, "issue_type")
    cs_labels_list, cs_conf = confusion_matrix(pred, gold, "claim_status")
    it_labels_list, it_conf = confusion_matrix(pred, gold, "issue_type")
    return {
        "n": len(gold),
        "per_column_accuracy": per_column_accuracy(pred, gold),
        "claim_status_accuracy": round(accuracy(pred, gold, "claim_status"), 4),
        "claim_status_macro_f1": round(cs_f1, 4),
        "claim_status_per_label": cs_labels,
        "claim_status_confusion": {"labels": cs_labels_list, "matrix": cs_conf},
        "issue_type_accuracy": round(accuracy(pred, gold, "issue_type"), 4),
        "issue_type_macro_f1": round(it_f1, 4),
        "issue_type_per_label": it_labels,
        "issue_type_confusion": {"labels": it_labels_list, "matrix": it_conf},
        "evidence_standard_met_accuracy": round(accuracy(pred, gold, "evidence_standard_met"), 4),
        "risk_flag_overlap": risk_flag_overlap(pred, gold),
    }
