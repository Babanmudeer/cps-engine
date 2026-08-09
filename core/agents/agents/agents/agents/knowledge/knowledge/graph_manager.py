from ..core.config import config
import json
import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, List

import psycopg2
from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)


class GraphManager:
    """Apache AGE Graph Manager for CPS Engine."""

    def __init__(self, graph_name: str):
        self.graph_name = graph_name

        self.db_config = {
    "dbname": config.database.dbname,
    "user": config.database.user,
    "password": config.database.password,
    "host": config.database.host,
    "port": config.database.port,
        }

        self._initialize_age()
        self._initialize_graph()

    @contextmanager
    def get_connection(self):
        """Create a PostgreSQL connection."""

        conn = None

        try:
            conn = psycopg2.connect(
                **self.db_config
            )

            conn.autocommit = False

            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute(
                    "SET search_path = ag_catalog, "
                    "'$user', public;"
                )

            yield conn

            conn.commit()

        except Exception as exc:
            if conn:
                conn.rollback()

            logger.error(
                "Database error: %s",
                exc,
            )
            raise

        finally:
            if conn:
                conn.close()

    def _initialize_age(self):
        """Initialize Apache AGE extension."""

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "CREATE EXTENSION IF NOT EXISTS age;"
                    )

                conn.commit()

            logger.info(
                "Apache AGE initialized successfully."
            )

        except Exception as exc:
            logger.error(
                "AGE initialization failed: %s",
                exc,
            )
            raise

    def _initialize_graph(self):
        """Create graph if it does not exist."""

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:

                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM ag_catalog.ag_graph
                            WHERE name = %s
                        );
                        """,
                        (self.graph_name,),
                    )

                    exists = cur.fetchone()[0]

                    if not exists:
                        logger.info(
                            "Creating graph: %s",
                            self.graph_name,
                        )

                        cur.execute(
                            "SELECT create_graph(%s);",
                            (self.graph_name,),
                        )

                        conn.commit()

        except Exception as exc:
            logger.error(
                "Graph initialization failed: %s",
                exc,
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=2,
            max=10,
        ),
    )
    def _execute_cypher(
        self,
        cypher: str,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query through Apache AGE."""

        results: List[Dict[str, Any]] = []

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:

                    full_query = f"""
                    SELECT *
                    FROM ag_catalog.cypher(
                        '{self.graph_name}',
                        $$
                        {cypher}
                        $$
                    )
                    AS (result ag_catalog.agtype);
                    """

                    cur.execute(full_query)

                    if cur.description:
                        rows = cur.fetchall()

                        for row in rows:
                            if row[0] is not None:
                                try:
                                    results.append(
                                        json.loads(
                                            str(row[0])
                                        )
                                    )
                                except json.JSONDecodeError:
                                    results.append(
                                        {
                                            "result": str(
                                                row[0]
                                            )
                                        }
                                    )

                    conn.commit()

            return results

        except Exception as exc:
            logger.error(
                "Cypher execution failed: %s",
                exc,
            )
            raise

    def execute_query(
        self,
        cypher: str,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query."""

        return self._execute_cypher(cypher)

    def get_schema_info(self) -> Dict[str, Any]:
        """Return basic graph schema information."""

        queries = {
            "nodes": (
                "MATCH (n) "
                "RETURN DISTINCT labels(n) AS Label, "
                "count(n) AS Count"
            ),
            "edges": (
                "MATCH ()-[r]->() "
                "RETURN DISTINCT type(r) AS Type, "
                "count(r) AS Count"
            ),
        }

        schema: Dict[str, Any] = {}

        for name, query in queries.items():
            try:
                schema[name] = self._execute_cypher(
                    query
                )
            except Exception as exc:
                logger.error(
                    "Schema query failed: %s",
                    exc,
                )
                schema[name] = []

        return schema

    def get_graph_stats(self) -> Dict[str, Any]:
        """Return graph node and edge counts."""

        try:
            node_stats = self._execute_cypher(
                "MATCH (n) "
                "RETURN count(n) AS TotalNodes"
            )

            edge_stats = self._execute_cypher(
                "MATCH ()-[r]->() "
                "RETURN count(r) AS TotalEdges"
            )

            total_nodes = 0
            total_edges = 0

            if node_stats:
                total_nodes = node_stats[0].get(
                    "TotalNodes",
                    0,
                )

            if edge_stats:
                total_edges = edge_stats[0].get(
                    "TotalEdges",
                    0,
                )

            return {
                "graph_name": self.graph_name,
                "total_nodes": total_nodes,
                "total_edges": total_edges,
            }

        except Exception as exc:
            logger.error(
                "Graph statistics failed: %s",
                exc,
            )

            return {
                "graph_name": self.graph_name,
                "total_nodes": 0,
                "total_edges": 0,
            }

    async def health_check(self) -> bool:
        """Check database and graph health."""

        try:
            self._execute_cypher(
                "MATCH (n) "
                "RETURN count(n) "
                "LIMIT 1"
            )

            return True

        except Exception as exc:
            logger.error(
                "Graph health check failed: %s",
                exc,
            )
            return False
