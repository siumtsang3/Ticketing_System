import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()


class DatabaseManager:
    def __init__(self):
        self.connection = None
        self._connect()

    def _connect(self):
        try:
            base_config = {
                "host": os.getenv("DB_HOST", "localhost"),
                "user": os.getenv("DB_USER", "root"),
                "password": os.getenv("DB_PASSWORD", ""),
                "port": int(os.getenv("DB_PORT", 3306)),
            }
            db_name = os.getenv("DB_NAME", "ticketing_system")

            # Connect without DB first to ensure the database exists
            tmp = mysql.connector.connect(**base_config)
            cur = tmp.cursor()
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            tmp.commit()
            cur.close()
            tmp.close()

            # Now connect with the target database
            self.connection = mysql.connector.connect(
                **base_config, database=db_name, autocommit=False
            )
        except Error as exc:
            raise ConnectionError(
                f"Cannot connect to MySQL: {exc}\n\n"
                "Please verify your .env DB_HOST / DB_USER / DB_PASSWORD settings."
            ) from exc

    # ------------------------------------------------------------------
    # Core execution helper
    # ------------------------------------------------------------------
    def execute(self, query, params=None, *, fetch=False, fetch_one=False):
        try:
            if not self.connection.is_connected():
                self._connect()

            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())

            if fetch:
                result = cursor.fetchall()
                cursor.close()
                return result
            elif fetch_one:
                result = cursor.fetchone()
                cursor.close()
                return result
            else:
                self.connection.commit()
                last_id = cursor.lastrowid
                cursor.close()
                return last_id
        except Error as exc:
            self.connection.rollback()
            raise RuntimeError(f"Database error: {exc}") from exc

    # ------------------------------------------------------------------
    # Table initialisation (called once on startup)
    # ------------------------------------------------------------------
    def initialize_tables(self):
        # ---- people ---------------------------------------------------
        self.execute("""
            CREATE TABLE IF NOT EXISTS people (
                person_id  INT AUTO_INCREMENT PRIMARY KEY,
                full_name  VARCHAR(100) NOT NULL,
                department VARCHAR(100) DEFAULT '',
                job_title  VARCHAR(100) DEFAULT '',
                email      VARCHAR(150) DEFAULT '',
                phone      VARCHAR(50)  DEFAULT '',
                is_active  TINYINT(1)   DEFAULT 1,
                created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # ---- projects -------------------------------------------------
        self.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id           INT AUTO_INCREMENT PRIMARY KEY,
                project_name         VARCHAR(200) NOT NULL,
                project_description  TEXT,
                business_requirements TEXT,
                start_date           DATE,
                expected_end_date    DATE,
                actual_end_date      DATE,
                status               VARCHAR(20) DEFAULT 'Planning',
                folder_path          VARCHAR(500) DEFAULT '',
                remarks              TEXT,
                created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # ---- tasks ----------------------------------------------------
        self.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id          INT AUTO_INCREMENT PRIMARY KEY,
                task_title       VARCHAR(300) NOT NULL,
                task_description TEXT,
                job_type         VARCHAR(60),
                priority         VARCHAR(20)  DEFAULT 'Medium',
                status           VARCHAR(30)  DEFAULT 'Open',
                requested_by     INT,
                follow_up_by     INT,
                requested_date   DATE,
                due_date         DATE,
                linked_project   INT,
                current_progress TEXT,
                remarks          TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (requested_by)   REFERENCES people(person_id)   ON DELETE SET NULL,
                FOREIGN KEY (follow_up_by)   REFERENCES people(person_id)   ON DELETE SET NULL,
                FOREIGN KEY (linked_project) REFERENCES projects(project_id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # ---- task_followers (many-to-many: a task handled by many people) ----
        self.execute("""
            CREATE TABLE IF NOT EXISTS task_followers (
                task_id   INT NOT NULL,
                person_id INT NOT NULL,
                PRIMARY KEY (task_id, person_id),
                FOREIGN KEY (task_id)   REFERENCES tasks(task_id)     ON DELETE CASCADE,
                FOREIGN KEY (person_id) REFERENCES people(person_id)  ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # One-time migration: seed followers from the legacy single
        # follow_up_by column for any task that has no followers yet.
        self.execute("""
            INSERT IGNORE INTO task_followers (task_id, person_id)
            SELECT t.task_id, t.follow_up_by
            FROM tasks t
            LEFT JOIN task_followers tf ON tf.task_id = t.task_id
            WHERE t.follow_up_by IS NOT NULL AND tf.task_id IS NULL
        """)

        # ---- task_updates (one-to-many: a task has a log of progress updates) ----
        self.execute("""
            CREATE TABLE IF NOT EXISTS task_updates (
                update_id      INT AUTO_INCREMENT PRIMARY KEY,
                task_id        INT NOT NULL,
                update_date    DATE NOT NULL,
                update_details TEXT,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

    # ------------------------------------------------------------------
    # Convenience helpers for dropdowns
    # ------------------------------------------------------------------
    def get_people_list(self, active_only=True):
        """Return list of dicts {person_id, full_name} for combo boxes."""
        q = "SELECT person_id, full_name FROM people"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY full_name"
        return self.execute(q, fetch=True)

    def get_projects_list(self, active_only=False):
        """Return list of dicts {project_id, project_name} for combo boxes."""
        q = "SELECT project_id, project_name FROM projects"
        if active_only:
            q += " WHERE status NOT IN ('Completed','Cancelled')"
        q += " ORDER BY project_name"
        return self.execute(q, fetch=True)

    def get_tasks_list(self):
        """Return list of dicts {task_id, task_title} for combo boxes/filters."""
        return self.execute(
            "SELECT task_id, task_title FROM tasks ORDER BY task_id DESC",
            fetch=True,
        )

    # ------------------------------------------------------------------
    # Task followers (many-to-many)
    # ------------------------------------------------------------------
    def get_task_follower_ids(self, task_id):
        """Return a list of person_ids assigned to (following) a task."""
        rows = self.execute(
            "SELECT person_id FROM task_followers WHERE task_id=%s",
            (task_id,), fetch=True,
        )
        return [r["person_id"] for r in rows]

    def set_task_followers(self, task_id, person_ids):
        """Replace the follower set for a task with the given person_ids."""
        self.execute("DELETE FROM task_followers WHERE task_id=%s", (task_id,))
        for pid in person_ids:
            if pid is not None:
                self.execute(
                    "INSERT IGNORE INTO task_followers (task_id, person_id) "
                    "VALUES (%s, %s)",
                    (task_id, pid),
                )

    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
