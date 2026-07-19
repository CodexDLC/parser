"""CLI для безопасной live-проверки OpenAI и Telegram."""

import argparse
import asyncio
import json
from dataclasses import asdict

from aibot.config import Settings
from aibot.services.integration_verification import (
    IntegrationCheckResult,
    IntegrationCheckStatus,
    IntegrationVerificationService,
)


def build_arg_parser() -> argparse.ArgumentParser:
    """Собрать аргументы operational verification."""

    parser = argparse.ArgumentParser(
        description="Verify real OpenAI and Telegram integrations without printing secrets.",
    )
    parser.add_argument(
        "--service",
        choices=("all", "openai", "telegram"),
        default="all",
        help="Select integrations to verify.",
    )
    parser.add_argument(
        "--telegram-source",
        help="Optional public channel username or t.me URL for one-message read check.",
    )
    parser.add_argument(
        "--publish-telegram-test",
        action="store_true",
        help="Explicitly publish one test message to TELEGRAM_TARGET_CHANNEL.",
    )
    return parser


async def run_checks(
    *,
    service_name: str,
    telegram_source: str | None,
    publish_telegram_test: bool,
) -> list[IntegrationCheckResult]:
    """Выполнить выбранные проверки через production adapters."""

    service = IntegrationVerificationService(Settings())
    results: list[IntegrationCheckResult] = []
    if service_name in {"all", "openai"}:
        results.append(await service.verify_openai())
    if service_name in {"all", "telegram"}:
        results.append(
            await service.verify_telegram(
                source=telegram_source,
                publish_test=publish_telegram_test,
            )
        )
    return results


def main() -> int:
    """Напечатать JSON без секретов и вернуть ненулевой код при blocker/failure."""

    args = build_arg_parser().parse_args()
    results = asyncio.run(
        run_checks(
            service_name=args.service,
            telegram_source=args.telegram_source,
            publish_telegram_test=args.publish_telegram_test,
        )
    )
    print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    return (
        0
        if all(result.status == IntegrationCheckStatus.PASSED for result in results)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
