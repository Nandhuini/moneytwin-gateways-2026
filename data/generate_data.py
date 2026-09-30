import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

users = [f"U{i:03d}" for i in range(1, 101)]

categories = [
    "Food", "Shopping", "Travel",
    "Entertainment", "Bills", "Healthcare"
]

rows = []

start_date = datetime(2026, 1, 1)

for user in users:
    for i in range(100):

        date = start_date + timedelta(
            days=random.randint(0, 270)
        )

        hour = random.randint(0, 23)
        minute = random.randint(0, 59)

        category = random.choice(categories)
        merchant = random.choice([
            "Swiggy", "Amazon", "Myntra",
            "Flipkart", "Uber", "Netflix",
            "Local Store", "Clinic"
        ])

        amount = random.uniform(100, 2500)

        # Payday spending spike
        if date.day in [1, 2, 3, 4, 5, 28, 29, 30, 31]:
            amount *= random.uniform(1.2, 2.0)

        # Late-night spending
        if hour >= 23 or hour <= 4:
            amount *= random.uniform(1.1, 1.8)

        # Shopping / return-prone category
        if category == "Shopping":
            merchant = random.choice([
                "Amazon", "Myntra", "Flipkart"
            ])

        # Recurring autopay
        if i % 25 == 0:
            merchant = random.choice([
                "Netflix", "Spotify",
                "Amazon Prime", "Gym"
            ])
            category = "Bills"
            amount = random.choice([199, 299, 499, 999])

        rows.append({
            "user_id": user,
            "transaction_id": f"T{i:05d}_{user}",
            "timestamp": date.replace(
                hour=hour,
                minute=minute
            ),
            "merchant": merchant,
            "category": category,
            "amount": round(amount, 2),
            "payment_method": random.choice([
                "UPI", "Card", "Wallet"
            ])
        })

df = pd.DataFrame(rows)

df.to_csv(
    "data/synthetic_transactions.csv",
    index=False
)

print(f"Generated {len(df)} transactions")
print("Saved to data/synthetic_transactions.csv")