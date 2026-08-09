import os
import json
import logging

import psycopg2

from typing import List, Dict
from contextlib import contextmanager
from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)


class GraphManager:
    """Apache AGE Graph Manager."""

    def __init__(self, graph_name: str):
        self.graph_name = graph_name

        self.db_config = {
            "dbname": os.getenv("DB_NAME", "cps_engine"),
            "user": os.getenv("DB_USER", "cps_user"),
            "password": os.getenv("DB_PASSWORD", "cps_pass"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
        }

        self._initialize_age()
        self._initialize_graph()

    @contextmanager
    def get_connection(self):
        conn = None

        try:
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = False

            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute(
                    "SET search_path = ag_catalog, '$user', public;"
                )

            yield conn

            conn.commit()

        except Exception as e:
            if conn:
                conn.rollback()

            logger.error(
                f"Database error: {str(e)}"
            )

            raise

        finally:
            if conn:
                conn.close()

    def _initialize_age(self):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "CREATE EXTENSION IF NOT EXISTS age;"
                    )

                conn.commit()

            logger.info(
                "✅ Apache AGE extension initialized"
            )

        except Exception as e:
            logger.error(
                f"AGE initialization failed: {str(e)}"
            )
            raise

    def _initialize_graph(self):
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
                            f"Creating graph: {self.graph_name}"
                        )

                        cur.execute(
                            "SELECT ag_catalog.create_graph(%s);",
                            (self.graph_name,),
                        )

                        conn.commit()

            if not exists:
                self._initialize_schema()

        except Exception as e:
            logger.error(
                f"Graph initialization failed: {str(e)}"
            )
            raise

    def _initialize_schema(self):
        logger.info(
            "Initializing CPS Engine graph schema..."
        )

        logger.info(
            "Graph schema initialization completed."
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=2,
            max=10
        ),
    )
    def _execute_cypher(
        self,
        cypher: str
    ) -> List[Dict]:

        results = []

        try:
            with self.get_connection() as conn:

                with conn.cursor() as cur:

                    full_query = f"""
                    SELECT *
                    FROM ag_catalog.cypher(
                        %s,
                        $$
                        {cypher}
                        $$
                    ) AS (
                        result ag_catalog.agtype
                    );
                    """

                    cur.execute(
                        full_query,
                        (self.graph_name,),
                    )

                    if cur.description:

                        rows = cur.fetchall()

                        for row in rows:

                            if row[0] is not None:

                                value = row[0]

                                try:
                                    results.append(
                                        json.loads(
                                            str(value)
                                        )
                                    )

                                except Exception:
                                    results.append(
                                        {
                                            "result": str(value)
                                        }
                                    )

                    conn.commit()

            return results

        except Exception as e:

            logger.error(
                f"Cypher execution failed: {str(e)}"
            )

            raise

    def execute_query(
        self,
        cypher: str
    ) -> List[Dict]:

        return self._execute_cypher(cypher)

    def validate_query(
        self,
        cypher: str
    ) -> bool:

        if not cypher.strip().upper().startswith(
            ("MATCH", "OPTIONAL", "RETURN")
        ):
            return False

        dangerous = [
            "DROP",
            "DELETE",
            "CREATE",
            "SET",
            "REMOVE",
            "MERGE",
            "ALTER",
        ]

        upper_query = cypher.upper()

        for word in dangerous:

            if word in upper_query:
                logger.warning(
                    f"Blocked dangerous query: {word}"
                )
                return False

        return True

    def get_schema_info(self) -> Dict:

        queries = {
            "nodes": (
                "MATCH (n) "
                "RETURN labels(n) AS Label, count(n) AS Count"
            ),
            "edges": (
                "MATCH ()-[r]->() "
                "RETURN type(r) AS Type, count(r) AS Count"
            ),
        }

        schema = {}

        for key, query in queries.items():

            try:
                schema[key] = self._execute_cypher(
                    query
                )

            except Exception:
                schema[key] = []

        return schema

    def get_graph_stats(self) -> Dict:

        try:

            node_stats = self._execute_cypher(
                "MATCH (n) RETURN count(n) AS TotalNodes"
            )

            edge_stats = self._execute_cypher(
                "MATCH ()-[r]->() RETURN count(r) AS TotalEdges"
            )

            return {
                "graph_name": self.graph_name,
                "total_nodes": (
                    node_stats[0].get(
                        "TotalNodes",
                        0
                    )
                    if node_stats
                    else 0
                ),
                "total_edges": (
                    edge_stats[0].get(
                        "TotalEdges",
                        0
                    )
                    if edge_stats
                    else 0
                ),
            }

        except Exception as e:

            logger.error(
                f"Graph statistics failed: {str(e)}"
            )

            return {}

    async def health_check(self) -> bool:

        try:

            self._execute_cypher(
                "MATCH (n) RETURN count(n) LIMIT 1"
            )

            return True

        except Exception:

            return False
