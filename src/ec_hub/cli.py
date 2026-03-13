"""ec-hub CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ec_hub.exporters import export_csv, export_json
from ec_hub.models import ListingCondition
from ec_hub.scrapers.ebay import EbayScraper

console = Console()


@click.group()
@click.version_option()
def main() -> None:
    """ec-hub: eBay商品データの収集・分析ツール."""


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

    _display_table(all_products)

    if output:
        output_path = Path(output)
        if output_path.suffix == ".csv":
            export_csv(all_products, output_path)
        else:
            from ec_hub.models import SearchResult

            result = SearchResult(query=query, total_results=len(all_products), products=all_products)
            export_json(result, output_path)
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


def _display_table(products: list) -> None:
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
