import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.models import AppSetting, Domain, Objective, Topic

DOMAIN_RE = re.compile(r"^## Domain (?P<number>\d+) [—-] (?P<name>.+?) \((?P<weight>\d+)%\)")
OBJECTIVE_RE = re.compile(r"^\| (?P<number>\d+\.\d+) \| (?P<title>.+?) \|")


@dataclass(frozen=True)
class ParsedDomain:
    id: str
    number: int
    name: str
    weight_percent: int
    objectives: tuple["ParsedObjective", ...]


@dataclass(frozen=True)
class ParsedObjective:
    id: str
    domain_id: str
    number: str
    title: str


def parse_objectives(path: Path) -> list[ParsedDomain]:
    domains: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if domain_match := DOMAIN_RE.match(raw_line):
            number = int(domain_match.group("number"))
            current = {
                "id": f"domain-{number}",
                "number": number,
                "name": domain_match.group("name").strip(),
                "weight_percent": int(domain_match.group("weight")),
                "objectives": [],
            }
            domains.append(current)
            continue

        if current is None:
            continue

        objective_match = OBJECTIVE_RE.match(raw_line)
        if not objective_match:
            continue

        objective_number = objective_match.group("number")
        if objective_number == "ID":
            continue
        title = objective_match.group("title").strip()
        current["objectives"].append(
            ParsedObjective(
                id=f"objective-{objective_number}",
                domain_id=str(current["id"]),
                number=objective_number,
                title=title,
            )
        )

    return [
        ParsedDomain(
            id=str(domain["id"]),
            number=int(domain["number"]),
            name=str(domain["name"]),
            weight_percent=int(domain["weight_percent"]),
            objectives=tuple(domain["objectives"]),
        )
        for domain in domains
    ]


def import_objectives(
    objectives_path: Path | None = None, settings: Settings | None = None
) -> dict[str, object]:
    settings = settings or get_settings()
    objectives_path = objectives_path or settings.project_root / "EXAM_OBJECTIVES.md"
    parsed_domains = parse_objectives(objectives_path)
    total_weight = sum(domain.weight_percent for domain in parsed_domains)
    weight_discrepancy = total_weight != 100

    with session(settings) as db:
        for domain in parsed_domains:
            domain_insert = sqlite_insert(Domain).values(
                id=domain.id,
                number=domain.number,
                name=domain.name,
                weight_percent=domain.weight_percent,
                updated_at=text("CURRENT_TIMESTAMP"),
            )
            db.execute(
                domain_insert.on_conflict_do_update(
                    index_elements=[Domain.id],
                    set_={
                        "number": domain_insert.excluded.number,
                        "name": domain_insert.excluded.name,
                        "weight_percent": domain_insert.excluded.weight_percent,
                        "updated_at": text("CURRENT_TIMESTAMP"),
                    },
                )
            )
            for objective in domain.objectives:
                objective_insert = sqlite_insert(Objective).values(
                    id=objective.id,
                    domain_id=objective.domain_id,
                    number=objective.number,
                    title=objective.title,
                    updated_at=text("CURRENT_TIMESTAMP"),
                )
                db.execute(
                    objective_insert.on_conflict_do_update(
                        index_elements=[Objective.id],
                        set_={
                            "domain_id": objective_insert.excluded.domain_id,
                            "number": objective_insert.excluded.number,
                            "title": objective_insert.excluded.title,
                            "updated_at": text("CURRENT_TIMESTAMP"),
                        },
                    )
                )
                topic_insert = sqlite_insert(Topic).values(
                    id=f"topic-{objective.number}",
                    objective_id=objective.id,
                    title=objective.title,
                    updated_at=text("CURRENT_TIMESTAMP"),
                )
                db.execute(
                    topic_insert.on_conflict_do_update(
                        index_elements=[Topic.id],
                        set_={
                            "objective_id": topic_insert.excluded.objective_id,
                            "title": topic_insert.excluded.title,
                            "updated_at": text("CURRENT_TIMESTAMP"),
                        },
                    )
                )

        for key, value in {
            "exam_weight_total_percent": json.dumps(total_weight),
            "exam_weight_discrepancy_flag": json.dumps(weight_discrepancy),
        }.items():
            setting_insert = sqlite_insert(AppSetting).values(
                key=key,
                value=value,
                updated_at=text("CURRENT_TIMESTAMP"),
            )
            db.execute(
                setting_insert.on_conflict_do_update(
                    index_elements=[AppSetting.key],
                    set_={
                        "value": setting_insert.excluded.value,
                        "updated_at": text("CURRENT_TIMESTAMP"),
                    },
                )
            )

    objective_count = sum(len(domain.objectives) for domain in parsed_domains)
    return {
        "domains_imported": len(parsed_domains),
        "objectives_imported": objective_count,
        "weight_total_percent": total_weight,
        "weight_discrepancy": weight_discrepancy,
    }
