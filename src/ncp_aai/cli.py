import argparse
import json
from pathlib import Path

from ncp_aai.config import get_settings
from ncp_aai.db import init_db
from ncp_aai.ingestion.service import ingest_local_file
from ncp_aai.objectives import import_objectives
from ncp_aai.rag.store import RagStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="ncp-aai")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")
    subparsers.add_parser("import-objectives")

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("path")
    ingest_parser.add_argument("--objective-id", action="append", default=[])
    ingest_parser.add_argument("--topic-id", action="append", default=[])

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("query")
    query_parser.add_argument("--k", type=int, default=5)

    args = parser.parse_args()
    settings = get_settings()
    init_db(settings)

    if args.command == "init-db":
        print(json.dumps({"status": "ok", "database": str(settings.sqlite_path)}, indent=2))
    elif args.command == "import-objectives":
        print(json.dumps(import_objectives(settings=settings), indent=2))
    elif args.command == "ingest":
        print(
            json.dumps(
                ingest_local_file(
                    Path(args.path),
                    objective_ids=args.objective_id,
                    topic_ids=args.topic_id,
                    settings=settings,
                ),
                indent=2,
            )
        )
    elif args.command == "query":
        print(json.dumps(RagStore(settings).query(args.query, k=args.k), indent=2))
