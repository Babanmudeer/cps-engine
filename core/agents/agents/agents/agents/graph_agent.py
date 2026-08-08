from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class GraphAgent:
    """Agent for Apache AGE knowledge graph operations."""

    def __init__(self, graph_manager):
        self.graph_manager = graph_manager

    def get_schema(self) -> Dict[str, Any]:
        """Return the graph schema."""
        try:
            return self.graph_manager.get_schema_info()
        except Exception as exc:
            logger.error(
                "Failed to get graph schema: %s",
                exc,
            )
            return {}

    def get_stats(self) -> Dict[str, Any]:
        """Return graph statistics."""
        try:
            return self.graph_manager.get_graph_stats()
        except Exception as exc:
            logger.error(
                "Failed to get graph statistics: %s",
                exc,
            )
            return {}

    async def health_check(self) -> bool:
        """Check whether the graph database is healthy."""
        try:
            return await self.graph_manager.health_check()
        except Exception as exc:
            logger.error(
                "Graph health check failed: %s",
                exc,
            )
            return False
