from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


def build_sample_tables(seed: int = 42) -> dict[str, pd.DataFrame]:
    """Generate deterministic ecommerce tables with realistic joins and business metrics."""

    rng = random.Random(seed)
    regions = ["North", "South", "East", "West"]
    segments = ["Consumer", "Corporate", "Small Business"]
    categories = ["Electronics", "Home", "Office", "Sports"]

    customers = pd.DataFrame(
        [
            {
                "customer_id": f"C{i:03d}",
                "region": regions[(i - 1) % len(regions)],
                "segment": segments[(i - 1) % len(segments)],
                "signup_date": date(2023, 1, 1) + timedelta(days=i * 5),
            }
            for i in range(1, 61)
        ]
    )

    products = pd.DataFrame(
        [
            {
                "product_id": f"P{i:03d}",
                "category": categories[(i - 1) % len(categories)],
                "product_name": f"{categories[(i - 1) % len(categories)]} Item {i}",
                "unit_cost": round(8 + (i % 11) * 3.25, 2),
                "unit_price": round(15 + (i % 11) * 5.75, 2),
            }
            for i in range(1, 25)
        ]
    )

    orders = []
    start = date(2024, 1, 1)
    for i in range(1, 501):
        customer = customers.iloc[rng.randrange(len(customers))]
        product = products.iloc[rng.randrange(len(products))]
        quantity = rng.randint(1, 6)
        discount = rng.choice([0.0, 0.0, 0.05, 0.10, 0.15])
        status = rng.choices(["completed", "returned", "cancelled"], [0.86, 0.08, 0.06])[0]
        order_date = start + timedelta(days=rng.randrange(730))
        revenue = round(product.unit_price * quantity * (1 - discount), 2)
        cost = round(product.unit_cost * quantity, 2)
        orders.append(
            {
                "order_id": f"O{i:04d}",
                "order_date": order_date,
                "customer_id": customer.customer_id,
                "product_id": product.product_id,
                "quantity": quantity,
                "discount": discount,
                "status": status,
                "revenue": revenue,
                "cost": cost,
            }
        )
    return {"customers": customers, "products": products, "orders": pd.DataFrame(orders)}


def write_sample_data(directory: str | Path) -> list[Path]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, frame in build_sample_tables().items():
        path = target / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    return paths


if __name__ == "__main__":
    write_sample_data(Path(__file__).resolve().parents[2] / "data" / "sample")

