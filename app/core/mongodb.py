"""MongoDB database connection and configuration."""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure
from typing import Optional
import os
from ..config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB database connection manager."""
    
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None


mongodb = MongoDB()


async def connect_to_mongo():
    """Create database connection with retry logic."""
    import asyncio
    max_retries = 15
    retry_delay = 2
    
    logger.info("=" * 50)
    logger.info("MongoDB Connection Configuration:")
    logger.info(f"  URI: {settings.mongodb_uri}")
    logger.info(f"  Database: {settings.mongodb_database}")
    logger.info("=" * 50)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"[MongoDB] Attempt {attempt + 1}/{max_retries}: Connecting to {settings.mongodb_uri}...")
            mongodb.client = AsyncIOMotorClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=5000
            )
            # Test connection
            await mongodb.client.admin.command('ping')
            mongodb.database = mongodb.client[settings.mongodb_database]
            logger.info("=" * 50)
            logger.info("SUCCESS: Connected to MongoDB!")
            logger.info(f"  Database: {settings.mongodb_database}")
            logger.info(f"  URI: {settings.mongodb_uri}")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"  Attempt {attempt + 1} failed: {str(e)}")
                logger.info(f"  Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("=" * 50)
                logger.error(f"CRITICAL: Failed to connect to MongoDB after {max_retries} attempts!")
                logger.error(f"  Last error: {str(e)}")
                logger.error("=" * 50)
                raise


async def close_mongo_connection():
    """Close database connection."""
    if mongodb.client:
        mongodb.client.close()
        logger.info("Disconnected from MongoDB")


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance."""
    if mongodb.database is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongo() first.")
    return mongodb.database

