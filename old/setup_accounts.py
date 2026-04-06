import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

import Scrapper.twscrape.twscrape as twscrape
from Scrapper.twscrape.twscrape import API
from config import settings


async def add_accounts(api: API, accounts_file: Path) -> None:
    if not accounts_file.exists():
        print(f"Accounts file not found: {accounts_file}")
        return

    with open(accounts_file, encoding="utf-8") as f:
        data = json.load(f)

    accounts = data.get("accounts", [])
    if not accounts:
        print("No accounts found in file")
        return

    print(f"Adding {len(accounts)} accounts...")
    for acc in accounts:
        username = acc.get("username")
        password = acc.get("password", "")
        email = acc.get("email", "")
        email_password = acc.get("email_password", "")
        cookies = acc.get("cookies")
        proxy = acc.get("proxy")
        mfa_code = acc.get("mfa_code")

        # Convert dict cookies to JSON string if needed
        if isinstance(cookies, dict):
            cookies = json.dumps(cookies)

        await api.pool.add_account(
            username=username,
            password=password,
            email=email,
            email_password=email_password,
            cookies=cookies,
            proxy=proxy,
            mfa_code=mfa_code,
        )

    print(f"Successfully added {len(accounts)} accounts")


async def login_accounts(api: API, usernames: list[str] | None = None, manual: bool = False) -> None:
    print("Logging in accounts...")
    if manual:
        twscrape.logger.warning("Manual mode: you will need to enter verification codes")

    result = await api.pool.login_all(usernames)
    print(f"Login results: {result}")


async def check_accounts(api: API) -> None:
    accounts = await api.pool.accounts_info()
    print(f"\n{'Username':<20} {'Logged In':<10} {'Active':<8} {'Last Used':<20} {'Total Req':<10}")
    print("-" * 80)

    for acc in accounts:
        last_used = acc["last_used"].strftime("%Y-%m-%d %H:%M:%S") if acc["last_used"] else "Never"
        print(f"{acc['username']:<20} {str(acc['logged_in']):<10} {str(acc['active']):<8} {last_used:<20} {acc['total_req']:<10}")


async def show_stats(api: API) -> None:
    stats = await api.pool.stats()
    print("\nAccount Pool Statistics:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


async def relogin_failed(api: API) -> None:
    print("Re-logging failed accounts...")
    result = await api.pool.relogin_failed()
    print(f"Re-login results: {result}")


async def delete_accounts(api: API, usernames: list[str]) -> None:
    print(f"Deleting accounts: {usernames}")
    await api.pool.delete_accounts(usernames)
    print("Accounts deleted")


def main():
    parser = argparse.ArgumentParser(description="Twitter Account Management Utility")
    parser.add_argument("--db", default=str(settings.DB_PATH), help="Path to accounts database")
    parser.add_argument("--accounts-file", type=Path, default=settings.ACCOUNTS_FILE,
                       help="Path to accounts JSON file")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    add_parser = subparsers.add_parser("add", help="Add accounts from JSON file")
    add_parser.add_argument("--accounts-file", type=Path, default=settings.ACCOUNTS_FILE,
                           help="Path to accounts JSON file")

    login_parser = subparsers.add_parser("login", help="Login all accounts")
    login_parser.add_argument("--manual", action="store_true", help="Manual email verification")
    login_parser.add_argument("usernames", nargs="*", help="Specific usernames to login")

    subparsers.add_parser("check", help="Check account statuses")

    subparsers.add_parser("stats", help="Show account pool statistics")

    subparsers.add_parser("relogin-failed", help="Re-login failed accounts")

    delete_parser = subparsers.add_parser("delete", help="Delete accounts")
    delete_parser.add_argument("usernames", nargs="+", help="Usernames to delete")

    args = parser.parse_args()

    api = API(pool=args.db)

    if args.command == "add":
        asyncio.run(add_accounts(api, args.accounts_file))
    elif args.command == "login":
        usernames = args.usernames if args.usernames else None
        asyncio.run(login_accounts(api, usernames, args.manual))
    elif args.command == "check":
        asyncio.run(check_accounts(api))
    elif args.command == "stats":
        asyncio.run(show_stats(api))
    elif args.command == "relogin-failed":
        asyncio.run(relogin_failed(api))
    elif args.command == "delete":
        asyncio.run(delete_accounts(api, args.usernames))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
