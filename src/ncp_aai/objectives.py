import json
import re
from dataclasses import dataclass
from pathlib import Path

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session

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

    with session(settings) as conn:
        for domain in parsed_domains:
            conn.execute(
                """
                INSERT INTO domains (id, number, name, weight_percent, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    number = excluded.number,
                    name = excluded.name,
                    weight_percent = excluded.weight_percent,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (domain.id, domain.number, domain.name, domain.weight_percent),
            )
            for objective in domain.objectives:
                conn.execute(
                    """
                    INSERT INTO objectives (id, domain_id, number, title, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        domain_id = excluded.domain_id,
                        number = excluded.number,
                        title = excluded.title,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (objective.id, objective.domain_id, objective.number, objective.title),
                )
                conn.execute(
                    """
                    INSERT INTO topics (id, objective_id, title, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        objective_id = excluded.objective_id,
                        title = excluded.title,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (f"topic-{objective.number}", objective.id, objective.title),
                )

        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES ('exam_weight_total_percent', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (json.dumps(total_weight),),
        )
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES ('exam_weight_discrepancy_flag', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (json.dumps(weight_discrepancy),),
        )

    objective_count = sum(len(domain.objectives) for domain in parsed_domains)
    return {
        "domains_imported": len(parsed_domains),
        "objectives_imported": objective_count,
        "weight_total_percent": total_weight,
        "weight_discrepancy": weight_discrepancy,
    }
