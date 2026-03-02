"""Seed the database with sample data for development."""
import asyncio

from sqlalchemy import text

from app.core.database import async_session


async def seed():
    async with async_session() as session:
        result = await session.execute(text("SELECT count(*) FROM datasets"))
        count = result.scalar()
        if count and count > 0:
            print("Database already seeded, skipping.")
            return

        await session.execute(
            text("""
                INSERT INTO datasets (name, description, format, source_type)
                VALUES
                    ('alpaca-demo', 'Stanford Alpaca instruction dataset (sample)', 'jsonl', 'upload'),
                    ('sentiment-reviews', 'Product review sentiment dataset', 'csv', 'upload')
            """)
        )
        await session.commit()
        print("Seed data inserted successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
