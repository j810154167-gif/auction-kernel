"""python -m datakit entry point."""

import sys
from datakit.cli.commands import build_parser, COMMAND_MAP
from datakit.guard import require_consensus


def main() -> None:
    # ── 未来函数风险门控: 首次调用必须人类确认 ──
    require_consensus()

    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
