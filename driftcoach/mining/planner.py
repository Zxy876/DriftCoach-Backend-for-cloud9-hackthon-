from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Literal
import time


# -----------------------------
# Data structures
# -----------------------------


@dataclass
class QueryTemplate:
    template_id: str
    query: str
    source_entity: str  # entity type the template consumes (e.g., series/player/team/tournament)
    target_entity: str  # entity type expected to expand (e.g., team/player/series)
    goal: str = "EXPAND_GRAPH"
    expected_signal: str = "new_id"


@dataclass
class TemplateStats:
    attempts: int = 0
    success: int = 0
    empty: int = 0
    schema_error: int = 0


@dataclass
class QueryAttempt:
    template_id: str
    substitutions: Dict[str, str]
    entity_id: Optional[str] = None
    result: Optional[str] = None  # success | schema_error | empty | substitution_error
    notes: Optional[str] = None
    discovered_ids: List[str] = field(default_factory=list)
    error_path: Optional[str] = None


@dataclass
class BlockedPaths:
    template_ids: Set[str] = field(default_factory=set)
    field_paths: Set[str] = field(default_factory=set)
    substitution_pairs: Set[str] = field(default_factory=set)

    def is_template_blocked(self, template_id: str) -> bool:
        return template_id in self.template_ids

    def is_substitution_blocked(self, template_id: str, entity_id: str) -> bool:
        key = f"{template_id}:{entity_id}"
        return key in self.substitution_pairs

    def block_template(self, template_id: str) -> None:
        self.template_ids.add(template_id)

    def block_field(self, field_path: str) -> None:
        self.field_paths.add(field_path)

    def block_substitution(self, template_id: str, entity_id: str) -> None:
        key = f"{template_id}:{entity_id}"
        self.substitution_pairs.add(key)


@dataclass
class EmptyResultTracker:
    empty_count: Dict[Tuple[str, str], int] = field(default_factory=dict)
    cooled: Set[Tuple[str, str]] = field(default_factory=set)
    cooldown_threshold: int = 2

    def record_empty(self, template_id: str, entity_id: str) -> None:
        key = (template_id, entity_id)
        self.empty_count[key] = self.empty_count.get(key, 0) + 1
        if self.empty_count[key] >= self.cooldown_threshold:
            self.cooled.add(key)

    def is_cooled(self, template_id: str, entity_id: str) -> bool:
        key = (template_id, entity_id)
        return key in self.cooled

    def reset_on_intensity_or_growth(self, cleared_keys: Optional[List[Tuple[str, str]]] = None) -> None:
        if cleared_keys:
            for key in cleared_keys:
                self.empty_count.pop(key, None)
                self.cooled.discard(key)
        else:
            self.empty_count.clear()
            self.cooled.clear()


@dataclass
class EntityPool:
    players: Set[str] = field(default_factory=set)
    series: Set[str] = field(default_factory=set)
    teams: Set[str] = field(default_factory=set)
    tournaments: Set[str] = field(default_factory=set)
    provenance: Dict[str, str] = field(default_factory=dict)  # entity_id -> source template

    def add(self, entity_type: str, entity_id: str, source: Optional[str] = None) -> bool:
        bucket = getattr(self, entity_type, None)
        if bucket is None:
            return False
        if entity_id not in bucket:
            bucket.add(entity_id)
            if source:
                self.provenance[entity_id] = source
            return True
        return False

    def as_counts(self) -> Dict[str, int]:
        return {
            "players": len(self.players),
            "series": len(self.series),
            "teams": len(self.teams),
            "tournaments": len(self.tournaments),
        }

    def entity_ids(self, entity_type: str) -> List[str]:
        bucket = getattr(self, entity_type, None)
        return list(bucket) if bucket is not None else []


@dataclass
class MiningContext:
    known_entities: EntityPool
    attempted_queries: List[QueryAttempt] = field(default_factory=list)
    blocked_paths: BlockedPaths = field(default_factory=BlockedPaths)
    empty_tracker: EmptyResultTracker = field(default_factory=EmptyResultTracker)
    iteration_state: Dict[str, int] = field(default_factory=lambda: {"depth": 0, "stagnation_rounds": 0})
    intensity: str = "L1"
    last_entity_counts: Dict[str, int] = field(default_factory=dict)
    template_stats: Dict[str, TemplateStats] = field(default_factory=dict)
    seeds: Dict[str, List[str]] = field(default_factory=dict)
    fresh_entities: Dict[str, List[str]] = field(default_factory=dict)
    api_error_history: List[float] = field(default_factory=list)
    consecutive_api_limited: int = 0


@dataclass
class MiningPlan:
    goal: str
    target_entity: str
    query_template: QueryTemplate
    substitutions: Dict[str, str]
    expected_signal: str
    notes: Optional[str] = None


@dataclass
class MiningSummary:
    terminated: bool
    reason: str
    termination_reason: Literal[
        "FRONTIER_EXHAUSTED",
        "ALL_TEMPLATES_BLOCKED",
        "ALL_COMBINATIONS_EMPTY",
        "INTENSITY_MAX_NO_PROGRESS",
        "API_CONSTRAINED",
    ]
    attempts: List[QueryAttempt]
    blocked: BlockedPaths
    cooled: List[Tuple[str, str]]
    entity_counts: Dict[str, int]
    seeds: Dict[str, List[str]] = field(default_factory=dict)
    discovered: Dict[str, List[str]] = field(default_factory=dict)
    tried_templates: List[Dict[str, str]] = field(default_factory=list)
    frontier_exhausted: bool = False


# -----------------------------
# Template registry (MIN only)
# -----------------------------


class TemplateRegistry:
    def __init__(self) -> None:
        self.templates: List[QueryTemplate] = []
        self._build_min_templates()

    def _build_min_templates(self) -> None:
        # MIN templates only; RICH not included in v1
        self.templates.extend(
            [
                QueryTemplate(
                    template_id="SERIES_BASIC_MIN",
                    query="query($seriesId: ID!){ series(id:$seriesId){ id } }",
                    source_entity="series",
                    target_entity="series",
                    expected_signal="non_empty_connection",
                ),
                QueryTemplate(
                    template_id="SERIES_TO_TEAMS_MIN",
                    query="query($seriesId: ID!){ series(id:$seriesId){ teams{ id } } }",
                    source_entity="series",
                    target_entity="team",
                ),
                QueryTemplate(
                    template_id="SERIES_TO_TOURNAMENT_MIN",
                    query="query($seriesId: ID!){ series(id:$seriesId){ tournament{ id } } }",
                    source_entity="series",
                    target_entity="tournament",
                    expected_signal="new_link",
                ),
                QueryTemplate(
                    template_id="TEAM_TO_PLAYERS_MIN",
                    query="query($teamId: ID!){ team(id:$teamId){ players{ id } } }",
                    source_entity="team",
                    target_entity="player",
                ),
                QueryTemplate(
                    template_id="PLAYER_TO_SERIES_MIN",
                    query="query($playerId: ID!){ player(id:$playerId){ series{ id } } }",
                    source_entity="player",
                    target_entity="series",
                ),
                QueryTemplate(
                    template_id="TEAM_TO_SERIES_MIN",
                    query="query($teamId: ID!){ series(filter:{ teamIds:[$teamId] }){ id } }",
                    source_entity="team",
                    target_entity="series",
                ),
                QueryTemplate(
                    template_id="TOURNAMENT_TO_SERIES_MIN",
                    query="query($tournamentId: ID!){ series(filter:{ tournamentIds:[$tournamentId] }){ id } }",
                    source_entity="tournament",
                    target_entity="series",
                ),
            ]
        )

    def for_entity(self, entity_type: str) -> List[QueryTemplate]:
        return [t for t in self.templates if t.source_entity == entity_type]


def _template_score(template_id: str, ctx: MiningContext) -> float:
    stats = ctx.template_stats.get(template_id)
    if not stats or stats.attempts == 0:
        return 0.0
    success_ratio = stats.success / stats.attempts
    schema_penalty = stats.schema_error / stats.attempts
    empty_penalty = stats.empty / stats.attempts
    return success_ratio - 0.5 * schema_penalty - 0.25 * empty_penalty


def build_stub_summary(seeds: Dict[str, List[str]], reason: str = "not_run") -> MiningSummary:
    return MiningSummary(
        terminated=False,
        reason=reason,
        termination_reason="FRONTIER_EXHAUSTED",
        attempts=[],
        blocked=BlockedPaths(),
        cooled=[],
        entity_counts={k: len(v) for k, v in seeds.items()},
        seeds=seeds,
        discovered=seeds,
        tried_templates=[],
        frontier_exhausted=True,
    )


# -----------------------------
# Planner
# -----------------------------


class MiningPlanner:
    TERMINATION_STAGNATION_ROUNDS = 2

    def __init__(self, registry: Optional[TemplateRegistry] = None) -> None:
        self.registry = registry or TemplateRegistry()

    def _maybe_reset_cooldown(self, ctx: MiningContext, counts: Dict[str, int]) -> None:
        if not ctx.last_entity_counts:
            return
        grew = any(counts[k] > ctx.last_entity_counts.get(k, 0) for k in counts.keys())
        if grew:
            ctx.empty_tracker.reset_on_intensity_or_growth()

    def _update_stagnation(self, ctx: MiningContext) -> None:
        counts = ctx.known_entities.as_counts()
        self._maybe_reset_cooldown(ctx, counts)
        if ctx.last_entity_counts and counts == ctx.last_entity_counts:
            ctx.iteration_state["stagnation_rounds"] = ctx.iteration_state.get("stagnation_rounds", 0) + 1
        else:
            ctx.iteration_state["stagnation_rounds"] = 0
        ctx.last_entity_counts = counts

    def _termination_check(self, ctx: MiningContext, has_candidate: bool) -> Optional[MiningSummary]:
        stagnation = ctx.iteration_state.get("stagnation_rounds", 0)
        cooled = list(ctx.empty_tracker.cooled)
        # If there are fresh entities, keep exploring
        any_fresh = any((vals for vals in ctx.fresh_entities.values()))
        if any_fresh:
            return None

        # API fatigue detection
        now = time.time()
        recent_api_errors = [ts for ts in ctx.api_error_history if now - ts <= 60]
        ctx.api_error_history = recent_api_errors
        if ctx.consecutive_api_limited >= 3 or len(recent_api_errors) >= 5:
            return self._build_summary(ctx, reason="api_constrained", frontier_exhausted=False, api_constrained=True)
        all_templates = self.registry.templates
        any_available = False
        for t in all_templates:
            if ctx.blocked_paths.is_template_blocked(t.template_id):
                continue
            for bucket_name in (t.source_entity,):
                for eid in ctx.known_entities.entity_ids(bucket_name):
                    if not ctx.empty_tracker.is_cooled(t.template_id, eid) and not ctx.blocked_paths.is_substitution_blocked(
                        t.template_id, eid
                    ):
                        any_available = True
                        break
                if any_available:
                    break
            if any_available:
                break

        if has_candidate or any_available:
            return None

        if stagnation >= self.TERMINATION_STAGNATION_ROUNDS or ctx.intensity == "L5":
            return self._build_summary(ctx, reason="stagnation_or_exhausted", frontier_exhausted=not any_available)
        return None

    def _build_summary(self, ctx: MiningContext, reason: str, frontier_exhausted: bool, api_constrained: bool = False) -> MiningSummary:
        seeds = ctx.seeds or {
            "players": list(ctx.known_entities.players),
            "series": list(ctx.known_entities.series),
            "teams": list(ctx.known_entities.teams),
            "tournaments": list(ctx.known_entities.tournaments),
        }
        discovered = {
            "players": list(ctx.known_entities.players),
            "series": list(ctx.known_entities.series),
            "teams": list(ctx.known_entities.teams),
            "tournaments": list(ctx.known_entities.tournaments),
        }
        tried_templates: List[Dict[str, str]] = []
        for att in ctx.attempted_queries:
            tried_templates.append(
                {
                    "template_id": att.template_id,
                    "substitutions": str(att.substitutions),
                    "result": att.result or "unknown",
                    "notes": att.notes or "",
                }
            )

        termination_reason = self._derive_termination_reason(ctx, frontier_exhausted, api_constrained)

        return MiningSummary(
            terminated=True,
            reason=reason,
            termination_reason=termination_reason,
            attempts=ctx.attempted_queries,
            blocked=ctx.blocked_paths,
            cooled=list(ctx.empty_tracker.cooled),
            entity_counts=ctx.known_entities.as_counts(),
            seeds=seeds,
            discovered=discovered,
            tried_templates=tried_templates,
            frontier_exhausted=frontier_exhausted,
        )

    def _derive_termination_reason(self, ctx: MiningContext, frontier_exhausted: bool, api_constrained: bool = False) -> Literal[
        "FRONTIER_EXHAUSTED",
        "ALL_TEMPLATES_BLOCKED",
        "ALL_COMBINATIONS_EMPTY",
        "INTENSITY_MAX_NO_PROGRESS",
        "API_CONSTRAINED",
    ]:
        if api_constrained:
            return "API_CONSTRAINED"
        all_template_ids = {t.template_id for t in self.registry.templates}
        blocked_templates = set(ctx.blocked_paths.template_ids)

        if blocked_templates and blocked_templates.issuperset(all_template_ids):
            return "ALL_TEMPLATES_BLOCKED"

        stagnation_rounds = ctx.iteration_state.get("stagnation_rounds", 0)
        if ctx.intensity == "L5" and stagnation_rounds >= self.TERMINATION_STAGNATION_ROUNDS:
            return "INTENSITY_MAX_NO_PROGRESS"

        if frontier_exhausted:
            return "FRONTIER_EXHAUSTED"

        if ctx.empty_tracker.cooled:
            return "ALL_COMBINATIONS_EMPTY"

        if any((vals for vals in ctx.fresh_entities.values())):
            return "FRONTIER_EXHAUSTED"

        return "FRONTIER_EXHAUSTED"

    def next_action(self, ctx: MiningContext) -> Tuple[Optional[MiningPlan], Optional[MiningSummary]]:
        # Update stagnation tracking first
        self._update_stagnation(ctx)

        # Candidate selection order guided by intensity (simple heuristic)
        entity_priority = ["series", "player", "team", "tournament"]
        if ctx.intensity in ("L4", "L5"):
            entity_priority = ["player", "series", "team", "tournament"]

        for entity_type in entity_priority:
            templates = self.registry.for_entity(entity_type)
            templates = sorted(
                templates,
                key=lambda t: _template_score(t.template_id, ctx),
                reverse=True,
            )
            for template in templates:
                if ctx.blocked_paths.is_template_blocked(template.template_id):
                    continue
                ids: List[str] = []
                fresh_list = ctx.fresh_entities.get(entity_type) or []
                if fresh_list:
                    eid = fresh_list.pop(0)
                    ids = [eid]
                    if not fresh_list:
                        ctx.fresh_entities.pop(entity_type, None)
                    else:
                        ctx.fresh_entities[entity_type] = fresh_list
                else:
                    ids = ctx.known_entities.entity_ids(entity_type)
                for eid in ids:
                    if ctx.blocked_paths.is_substitution_blocked(template.template_id, eid):
                        continue
                    if ctx.empty_tracker.is_cooled(template.template_id, eid):
                        continue
                    substitutions = self._build_substitutions(template, eid)
                    if substitutions is None:
                        continue
                    plan = MiningPlan(
                        goal=template.goal,
                        target_entity=template.target_entity,
                        query_template=template,
                        substitutions=substitutions,
                        expected_signal=template.expected_signal,
                        notes=f"intensity={ctx.intensity}",
                    )
                    return plan, None

        # No candidate; check termination
        summary = self._termination_check(ctx, has_candidate=False)
        if summary:
            return None, summary
        return None, None

    def record_attempt_result(self, ctx: MiningContext, attempt: QueryAttempt) -> None:
        ctx.attempted_queries.append(attempt)
        stats = ctx.template_stats.setdefault(attempt.template_id, TemplateStats())
        stats.attempts += 1
        if attempt.result == "success":
            stats.success += 1
        elif attempt.result == "schema_error":
            stats.schema_error += 1
        elif attempt.result == "empty":
            stats.empty += 1

    @staticmethod
    def _build_substitutions(template: QueryTemplate, entity_id: str) -> Optional[Dict[str, str]]:
        if template.source_entity == "series":
            return {"seriesId": entity_id}
        if template.source_entity == "player":
            return {"playerId": entity_id}
        if template.source_entity == "team":
            return {"teamId": entity_id}
        if template.source_entity == "tournament":
            return {"tournamentId": entity_id}
        return None


__all__ = [
    "MiningContext",
    "MiningPlan",
    "MiningSummary",
    "EntityPool",
    "TemplateRegistry",
    "TemplateStats",
    "BlockedPaths",
    "EmptyResultTracker",
    "MiningPlanner",
    "QueryTemplate",
    "QueryAttempt",
    "build_stub_summary",
]
