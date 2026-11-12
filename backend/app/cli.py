"""运维 CLI：建表、点表导入、演示数据、单次采集、配置检查。"""

import argparse
import json
import logging
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.init_db import init_db
from app.db.seed import import_points, seed_demo
from app.services.collector import run_poll_cycle

logger = logging.getLogger(__name__)


def _mask_database_url(url: str) -> str:
    if url.startswith("sqlite"):
        return url
    parsed = urlparse(url)
    if parsed.password:
        return url.replace(parsed.password, "••••••", 1)
    return url


def _cmd_init_db(args) -> int:
    init_db()
    print("数据库结构已初始化")
    return 0


def _cmd_import_points(args) -> int:
    init_db()
    stats = import_points(args.path)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def _cmd_seed_demo(args) -> int:
    init_db()
    created = seed_demo(reset=args.reset)
    print("演示数据已生成" if created else "已有数据，未重复生成（使用 --reset 重建）")
    return 0


def _cmd_collect_once(args) -> int:
    init_db()
    summary = run_poll_cycle()
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _cmd_check_config(args) -> int:
    payload = {
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "database_url": _mask_database_url(settings.database_url),
        "collector_mode": settings.collector_mode,
        "run_collector": settings.run_collector,
        "poll_interval_minutes": settings.poll_interval_minutes,
        "retention_days": settings.retention_days,
        "auth_mode": settings.auth_mode,
        "feishu_configured": settings.feishu_configured,
        "feishu_masked_webhook": settings.masked_webhook(),
        "lora": {
            "frequency_mhz": settings.lora_frequency_mhz,
            "baud_rate": settings.lora_baud_rate,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="MotorPulse 运维命令")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="创建数据库表与默认配置")
    init_parser.set_defaults(func=_cmd_init_db)

    import_parser = subparsers.add_parser("import-points", help="导入 YAML 点表")
    import_parser.add_argument("path", help="点表 YAML 路径")
    import_parser.set_defaults(func=_cmd_import_points)

    demo_parser = subparsers.add_parser("seed-demo", help="生成 6 台电机演示数据")
    demo_parser.add_argument("--reset", action="store_true", help="清空现有业务数据后重建")
    demo_parser.set_defaults(func=_cmd_seed_demo)

    collect_parser = subparsers.add_parser("collect-once", help="立即执行一轮采集")
    collect_parser.set_defaults(func=_cmd_collect_once)

    check_parser = subparsers.add_parser("check-config", help="打印当前配置")
    check_parser.set_defaults(func=_cmd_check_config)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging(settings.log_level)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
