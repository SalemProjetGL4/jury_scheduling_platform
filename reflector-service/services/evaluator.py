from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Iterable, List

from config import settings

try:
    import redis
except Exception:  # pragma: no cover - optional
    redis = None


@dataclass
class CompromisedReview:
    solution_index: int
    rating: int
    violations_count: int
    total_penalty: float
    violated_soft_constraints: list[dict[str, Any]]
    explanation: str


class ReflectorEvaluator:
    """Evaluator responsible for scoring, acceptance, diagnostics, and strategic relaxations."""

    # Human cost multipliers for rules (higher => worse to violate)
    RULE_HUMAN_COST: dict[str, float] = {
        "prefer_professor_role": 2.0,
        "prefer_project_session": 1.0,
        "avoid_professor_session": 1.0,
        "penalize_professor_project": 1.5,
        "prefer_morning": 0.8,
    }

    def __init__(self) -> None:
        self.redis_client = None
        if redis and getattr(settings, "redis_url", None):
            try:
                self.redis_client = redis.from_url(settings.redis_url)
            except Exception:
                self.redis_client = None

    def _violation_total(self, violations: Iterable[dict[str, Any]]) -> float:
        total = 0.0
        for v in violations:
            pw = v.get("penalty_weighted")
            if pw is None:
                p = v.get("penalty")
                if p is not None:
                    total += float(p) / 100
            else:
                total += float(pw)
        return total

    def _human_cost_multiplier(self, rule: str) -> float:
        return float(self.RULE_HUMAN_COST.get(rule, 1.0))

    def score_solutions(self, solutions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return list of review dicts with ratings and total_penalty.

        Each review includes: solution_index, rating, violations_count, total_penalty,
        violated_soft_constraints and explanation.
        """
        reviews: list[dict[str, Any]] = []

        for sol in solutions:
            idx = int(sol.get("solution_index") or 0)
            violations = list(sol.get("unsatisfied_soft_constraints") or [])
            violations_count = len(violations)
            raw_total = self._violation_total(violations)

            # compute a human-weighted total
            weighted_total = 0.0
            for v in violations:
                rule = str(v.get("rule") or "")
                multiplier = self._human_cost_multiplier(rule)
                # penalty_weighted already includes WEIGHT_SCALE division
                penalty = float(v.get("penalty_weighted") or (v.get("penalty") or 0) / 100)
                weighted_total += penalty * multiplier

            # fallback to raw_total if no violations
            total_penalty = weighted_total if weighted_total > 0 else raw_total

            # rating formula: base 100, penalize count and weighted penalty.
            # Use log scale for the penalty so the score stays meaningful for
            # large problem sizes where raw penalties can be in the thousands.
            penalty_score = min(70, int(round(math.log1p(total_penalty) * 5)))
            violation_score = min(30, violations_count * 5)
            rating = max(0, min(100, 100 - violation_score - penalty_score))

            explanation = self._build_explanation(violations)

            reviews.append(
                {
                    "solution_index": idx,
                    "rating": rating,
                    "violations_count": violations_count,
                    "total_penalty": round(total_penalty, 2),
                    "violated_soft_constraints": violations,
                    "explanation": explanation,
                }
            )

        # sort reviews by rating desc, penalty asc, count asc, index asc
        reviews.sort(key=lambda r: (-r["rating"], r["total_penalty"], r["violations_count"], r["solution_index"]))
        return reviews

    def is_acceptable(self, solution: dict[str, Any], threshold: float = 0.5) -> bool:
        """Return True if a SOFT_OPTIMAL solution is acceptable under threshold.

        Threshold is expressed in weighted penalty units (same units as penalty_weighted).
        """
        if str(solution.get("status", "")).upper() not in {"SOFT_OPTIMAL", "OPTIMAL"}:
            return False
        violations = list(solution.get("unsatisfied_soft_constraints") or [])
        total = self._violation_total(violations)
        return total <= float(threshold)

    def analyze_infeasible(self, failed_constraints: list[dict[str, Any]], solver_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform simple root-cause analysis on failed hard constraints.

        Returns a dict with 'bottleneck' (str) and 'evidence' (list).
        """
        # Count occurrences by key fields (professor_id, project_id)
        prof_counts: dict[Any, int] = {}
        proj_counts: dict[Any, int] = {}
        for f in failed_constraints:
            details = f.get("details") or {}
            pid = details.get("professor_id")
            if pid is not None:
                prof_counts[pid] = prof_counts.get(pid, 0) + 1
            pr = details.get("project_id")
            if pr is not None:
                proj_counts[pr] = proj_counts.get(pr, 0) + 1

        bottleneck = None
        evidence: list[dict[str, Any]] = []
        if prof_counts:
            top_prof = max(prof_counts.items(), key=lambda x: x[1])
            bottleneck = f"Professor {top_prof[0]} appears in {top_prof[1]} failing constraints"
            evidence.append({"professor_id": top_prof[0], "count": top_prof[1]})
        elif proj_counts:
            top_proj = max(proj_counts.items(), key=lambda x: x[1])
            bottleneck = f"Project {top_proj[0]} appears in {top_proj[1]} failing constraints"
            evidence.append({"project_id": top_proj[0], "count": top_proj[1]})
        else:
            bottleneck = "No clear bottleneck identified from failed constraints"

        return {"bottleneck": bottleneck, "evidence": evidence}

    def suggest_weight_adjustments(self, solutions: list[dict[str, Any]], solver_payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Propose soft weight adjustments to enable next solver iteration.

        Returns a list of adjustment suggestions: {rule, current_weight?, suggested_weight, reason}
        Will consult Redis cache (if configured) to avoid repeating suggestions.
        """
        # Tally violations by rule
        tally: dict[str, int] = {}
        for s in solutions:
            for v in s.get("unsatisfied_soft_constraints") or []:
                r = str(v.get("rule") or "unknown")
                tally[r] = tally.get(r, 0) + 1

        # propose adjustments for top offenders
        suggestions: list[dict[str, Any]] = []
        for rule, count in sorted(tally.items(), key=lambda x: -x[1])[:5]:
            # build a signature to check in Redis
            sig = hashlib.sha256(json.dumps({"rule": rule, "count": count}, sort_keys=True).encode()).hexdigest()
            if self._was_suggested(sig):
                continue

            # try to extract current weight from solver_payload soft rules
            current = None
            if solver_payload:
                for r in (solver_payload.get("constraint_rules") or solver_payload.get("soft_rules") or []):
                    if r.get("rule") == rule:
                        current = r.get("weight")
                        break

            # default reduction: halve the weight (or set to 0 if weight small)
            suggested = None
            if current is None:
                suggested = 0.5
            else:
                try:
                    current_f = float(current)
                    if current_f <= 0.5:
                        suggested = 0.0
                    else:
                        suggested = round(current_f / 2.0, 2)
                except Exception:
                    suggested = 0.5

            entry = {"rule": rule, "current_weight": current, "suggested_weight": suggested, "reason": f"Rule violated {count} times"}
            suggestions.append(entry)
            self._record_suggestion(sig)

        return suggestions

    def _was_suggested(self, signature: str) -> bool:
        if not self.redis_client:
            return False
        try:
            return bool(self.redis_client.get(f"reflector:suggestion:{signature}"))
        except Exception:
            return False

    def _record_suggestion(self, signature: str) -> None:
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(f"reflector:suggestion:{signature}", 60 * 60 * 24, "1")
        except Exception:
            pass

    def _build_explanation(self, violations: Iterable[dict[str, Any]]) -> str:
        items = []
        for v in list(violations)[:3]:
            rule = v.get("rule")
            payload = v.get("payload") or {}
            if payload:
                items.append(f"{rule} {json.dumps(payload, ensure_ascii=True)}")
            else:
                items.append(str(rule))
        if not items:
            return "No soft constraint violations."
        s = "; ".join(items)
        if len(list(violations)) > 3:
            s = f"{s}; and {len(list(violations)) - 3} more"
        return f"Violations: {s}."
