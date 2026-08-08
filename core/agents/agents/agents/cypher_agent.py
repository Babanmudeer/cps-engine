from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)


class CypherAgent:
    """Safe Cypher Agent for Apache AGE graph operations."""

    def __init__(self, graph_manager):
        self.graph_manager = graph_manager

    async def execute_query(
        self,
        cypher: str,
    ) -> List[Dict[str, Any]]:
        """Execute a validated read-only Cypher query."""

        if not self.validate_query(cypher):
            logger.warning(
                "Blocked unsafe Cypher query"
            )
            return []

        try:
            return self.graph_manager.execute_query(cypher)

        except Exception as exc:
            logger.error(
                "Cypher execution failed: %s",
                exc,
            )
            return []

    def validate_query(self, cypher: str) -> bool:
        """Allow only read-only Cypher operations."""

        if not cypher or not cypher.strip():
            return False

        query = cypher.strip()
        upper_query = query.upper()

        allowed_starts = (
            "MATCH",
            "OPTIONAL MATCH",
            "RETURN",
            "WITH",
        )

        if not upper_query.startswith(
            allowed_starts
        ):
            return False

        dangerous_keywords = [
            "DROP",
            "DELETE",
            "CREATE",
            "SET",
            "REMOVE",
            "MERGE",
            "ALTER",
            "TRUNCATE",
            "CALL",
        ]

        for keyword in dangerous_keywords:
            if keyword in upper_query:
                logger.warning(
                    "Blocked dangerous Cypher keyword: %s",
                    keyword,
                )
                return False

        return True
