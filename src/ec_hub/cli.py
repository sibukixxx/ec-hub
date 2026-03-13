"""ec-hub CLI - eBay輸出転売 自動化システム."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.exporters import export_csv, export_json
from ec_hub.models import ListingCondition, SearchResult
from ec_hub.modules.notifier import Notifier
from ec_hub.modules.profit_tracker import ProfitTracker
from ec_hub.scrapers.ebay import EbayScraper

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.group()
@click.version_option()
@click.option("--verbose", "-v", is_flag=True, help="詳細ログ出力")
def main(verbose: bool) -> None:
    """ec-hub: eBay輸出転売 自動化システム."""
    _setup_logging(verbose)


# === eBay検索コマンド群 ===


@main.command()
@click.argument("query")
@click.option("--pages", "-p", default=1, help="取得ページ数")
@click.option("--min-price", type=float, help="最低価格")
@click.option("--max-price", type=float, help="最高価格")
@click.option(
    "--condition",
    type=click.Choice(["new", "used", "refurbished", "open_box", "for_parts"]),
    help="商品状態フィルタ",
)
@click.option(
    "--sort",
    type=click.Choice(["best_match", "price_asc", "price_desc", "date_desc", "newly_listed"]),
    default="best_match",
    help="ソート順",
)
@click.option("--output", "-o", type=click.Path(), help="出力ファイルパス (.csv or .json)")
@click.option("--site", default="com", help="eBayサイト (com, co.uk, de, co.jp など)")
def search(
    query: str,
    pages: int,
    min_price: float | None,
    max_price: float | None,
    condition: str | None,
    sort: str,
    output: str | None,
    site: str,
) -> None:
    """eBayで商品を検索する."""
    asyncio.run(_search(query, pages, min_price, max_price, condition, sort, output, site))


async def _search(
    query: str,
    pages: int,
    min_price: float | None,
    max_price: float | None,
    condition: str | None,
    sort: str,
    output: str | None,
    site: str,
) -> None:
    condition_map = {
        "new": ListingCondition.NEW,
        "used": ListingCondition.USED,
        "refurbished": ListingCondition.REFURBISHED,
        "open_box": ListingCondition.OPEN_BOX,
        "for_parts": ListingCondition.FOR_PARTS,
    }
    cond = condition_map.get(condition) if condition else None

    all_products = []
    async with EbayScraper(site=site) as scraper:
        for page in range(1, pages + 1):
            console.print(f"[bold blue]ページ {page}/{pages} を取得中...[/]")
            result = await scraper.search(
                query,
                page=page,
                min_price=min_price,
                max_price=max_price,
                condition=cond,
                sort=sort,
            )
            all_products.extend(result.products)
            console.print(f"  {len(result.products)} 件取得 (合計: {result.total_results} 件)")

    if not all_products:
        console.print("[yellow]商品が見つかりませんでした。[/]")
        return

    _display_products_table(all_products)

    if output:
        output_path = Path(output)
        if output_path.suffix == ".csv":
            export_csv(all_products, output_path)
        else:
            sr = SearchResult(query=query, total_results=len(all_products), products=all_products)
            export_json(sr, output_path)
        console.print(f"\n[green]結果を {output_path} に保存しました。({len(all_products)} 件)[/]")


@main.command()
@click.argument("item_id")
@click.option("--site", default="com", help="eBayサイト")
@click.option("--output", "-o", type=click.Path(), help="出力ファイルパス (.json)")
def item(item_id: str, site: str, output: str | None) -> None:
    """商品IDから詳細情報を取得する."""
    asyncio.run(_item(item_id, site, output))


async def _item(item_id: str, site: str, output: str | None) -> None:
    async with EbayScraper(site=site) as scraper:
        console.print(f"[bold blue]商品 {item_id} の情報を取得中...[/]")
        product = await scraper.get_item(item_id)

    if not product:
        console.print("[red]商品が見つかりませんでした。[/]")
        return

    console.print(f"\n[bold]{product.title}[/]")
    console.print(f"  価格: {product.price} {product.currency}")
    console.print(f"  状態: {product.condition.value}")
    console.print(f"  URL: {product.url}")
    if product.seller:
        console.print(f"  出品者: {product.seller.name}")

    if output:
        output_path = Path(output)
        export_json([product], output_path)
        console.print(f"\n[green]結果を {output_path} に保存しました。[/]")


# === 利益計算コマンド ===


@main.command()
@click.option("--cost", required=True, type=int, help="仕入れ価格（円）")
@click.option("--price", required=True, type=float, help="eBay出品価格（ドル）")
@click.option("--weight", default=500, type=int, help="重量（g）")
@click.option("--dest", default="US", help="配送先国コード")
def calc(cost: int, price: float, weight: int, dest: str) -> None:
    """利益シミュレーションを行う."""
    asyncio.run(_calc(cost, price, weight, dest))


async def _calc(cost: int, price: float, weight: int, dest: str) -> None:
    settings = load_settings()
    fee_rules = load_fee_rules()
    async with Database(settings.get("database", {}).get("path", "db/ebay.db")) as db:
        tracker = ProfitTracker(db, settings, fee_rules)
        fx_rate = await tracker.get_fx_rate()
        breakdown = tracker.calc_net_profit(
            jpy_cost=cost,
            ebay_price_usd=price,
            weight_g=weight,
            destination=dest,
            fx_rate=fx_rate,
        )

    table = Table(title="利益シミュレーション", show_lines=True)
    table.add_column("項目", style="bold")
    table.add_column("金額", justify="right")

    table.add_row("eBay売価", f"${breakdown.ebay_price_usd:.2f}")
    table.add_row("為替レート", f"¥{breakdown.fx_rate:.2f}/USD")
    table.add_row("円換算売上", f"¥{breakdown.jpy_revenue:,}")
    table.add_row("─────", "─────")
    table.add_row("仕入れ価格", f"¥{breakdown.jpy_cost:,}")
    table.add_row("eBay手数料 (13.25%)", f"¥{breakdown.ebay_fee:,}")
    table.add_row("Payoneer手数料 (2%)", f"¥{breakdown.payoneer_fee:,}")
    table.add_row("国際送料", f"¥{breakdown.shipping_cost:,}")
    table.add_row("梱包資材", f"¥{breakdown.packing_cost:,}")
    table.add_row("為替バッファ (3%)", f"¥{breakdown.fx_buffer:,}")
    table.add_row("─────", "─────")
    table.add_row("費用合計", f"¥{breakdown.total_cost:,}")

    profit_style = "green" if breakdown.net_profit > 0 else "red"
    table.add_row(f"[{profit_style}]純利益[/]", f"[{profit_style}]¥{breakdown.net_profit:,}[/]")
    table.add_row(f"[{profit_style}]利益率[/]", f"[{profit_style}]{breakdown.margin_rate:.1%}[/]")

    console.print(table)

    if breakdown.margin_rate < 0.30:
        console.print("\n[yellow]利益率30%未満のため、自動出品対象外です。[/]")
    else:
        console.print("\n[green]利益率30%以上 - 出品候補として適格です。[/]")


# === リサーチコマンド ===


@main.command()
@click.argument("queries", nargs=-1)
@click.option("--pages", "-p", default=1, help="eBay検索のページ数")
def research(queries: tuple[str, ...], pages: int) -> None:
    """eBay売れ筋 ⇔ Amazon/楽天の価格差リサーチを実行する.

    QUERIES: 検索キーワード（複数指定可）。省略時はデフォルトキーワードを使用。

    例: ec-hub research "anime figure" "japanese pottery"
    """
    asyncio.run(_research(list(queries) if queries else None, pages))


async def _research(queries: list[str] | None, pages: int) -> None:
    from ec_hub.modules.researcher import Researcher

    settings = load_settings()
    fee_rules = load_fee_rules()
    async with Database(settings.get("database", {}).get("path", "db/ebay.db")) as db:
        researcher = Researcher(db, settings, fee_rules)
        console.print("[bold blue]リサーチを開始...[/]")
        count = await researcher.run(queries, pages=pages)
        console.print(f"\n[green]リサーチ完了: {count} 件の候補を登録しました。[/]")

        if count > 0:
            rows = await db.get_candidates(status="pending", limit=count)
            table = Table(title="新規候補", show_lines=True)
            table.add_column("ID", style="dim", width=5)
            table.add_column("商品名", max_width=35)
            table.add_column("仕入元", width=8)
            table.add_column("仕入", justify="right")
            table.add_column("eBay", justify="right")
            table.add_column("純利益", justify="right")
            table.add_column("利益率", justify="right")

            for r in rows:
                margin = r.get("margin_rate")
                margin_str = f"{margin:.0%}" if margin else "N/A"
                profit = r.get("net_profit_jpy")
                profit_str = f"¥{profit:,}" if profit else "N/A"
                table.add_row(
                    str(r["id"]),
                    r.get("title_jp", "")[:35],
                    r.get("source_site", ""),
                    f"¥{r.get('cost_jpy', 0):,}",
                    f"${r.get('ebay_price_usd', 0):.2f}",
                    profit_str,
                    margin_str,
                )
            console.print(table)


# === 候補管理コマンド ===


@main.command()
@click.option("--status", type=click.Choice(["pending", "approved", "rejected", "listed"]), help="ステータスフィルタ")
@click.option("--limit", default=20, help="表示件数")
def candidates(status: str | None, limit: int) -> None:
    """リサーチ候補一覧を表示する."""
    asyncio.run(_candidates(status, limit))


async def _candidates(status: str | None, limit: int) -> None:
    settings = load_settings()
    async with Database(settings.get("database", {}).get("path", "db/ebay.db")) as db:
        rows = await db.get_candidates(status=status, limit=limit)

    if not rows:
        console.print("[yellow]候補がありません。[/]")
        return

    table = Table(title="リサーチ候補", show_lines=True)
    table.add_column("ID", style="dim", width=5)
    table.add_column("商品名", max_width=40)
    table.add_column("仕入", justify="right")
    table.add_column("eBay", justify="right")
    table.add_column("純利益", justify="right")
    table.add_column("利益率", justify="right")
    table.add_column("ステータス", width=10)

    for r in rows:
        margin = r.get("margin_rate")
        margin_str = f"{margin:.0%}" if margin else "N/A"
        profit = r.get("net_profit_jpy")
        profit_str = f"¥{profit:,}" if profit else "N/A"
        table.add_row(
            str(r["id"]),
            r.get("title_jp", "")[:40],
            f"¥{r.get('cost_jpy', 0):,}",
            f"${r.get('ebay_price_usd', 0):.2f}",
            profit_str,
            margin_str,
            r.get("status", ""),
        )

    console.print(table)


# === 注文管理コマンド ===


@main.command()
@click.option("--status", type=click.Choice([
    "awaiting_purchase", "purchased", "shipped", "delivered", "completed"
]), help="ステータスフィルタ")
@click.option("--limit", default=20, help="表示件数")
def orders(status: str | None, limit: int) -> None:
    """注文一覧を表示する."""
    asyncio.run(_orders(status, limit))


async def _orders(status: str | None, limit: int) -> None:
    settings = load_settings()
    async with Database(settings.get("database", {}).get("path", "db/ebay.db")) as db:
        rows = await db.get_orders(status=status, limit=limit)

    if not rows:
        console.print("[yellow]注文がありません。[/]")
        return

    table = Table(title="注文一覧", show_lines=True)
    table.add_column("ID", style="dim", width=5)
    table.add_column("eBay注文ID", width=20)
    table.add_column("売価", justify="right")
    table.add_column("純利益", justify="right")
    table.add_column("ステータス", width=18)
    table.add_column("注文日", width=12)

    for r in rows:
        profit = r.get("net_profit_jpy")
        profit_str = f"¥{profit:,}" if profit else "—"
        ordered = r.get("ordered_at", "")[:10]
        table.add_row(
            str(r["id"]),
            r.get("ebay_order_id", ""),
            f"${r.get('sale_price_usd', 0):.2f}",
            profit_str,
            r.get("status", ""),
            ordered,
        )

    console.print(table)


# === ヘルパー関数 ===


def _display_products_table(products: list) -> None:
    """商品リストをテーブル形式で表示する."""
    table = Table(title="検索結果", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("タイトル", max_width=50)
    table.add_column("価格", justify="right")
    table.add_column("状態", width=12)
    table.add_column("送料", justify="right", width=10)

    for i, p in enumerate(products[:50], 1):
        price_str = f"${p.price:.2f}" if p.price else "N/A"
        shipping_str = "無料" if p.shipping and p.shipping.free_shipping else ""
        if not shipping_str and p.shipping and p.shipping.cost:
            shipping_str = f"${p.shipping.cost:.2f}"
        table.add_row(
            str(i),
            p.title[:50],
            price_str,
            p.condition.value,
            shipping_str,
        )

    console.print(table)


if __name__ == "__main__":
    main()
