"""Fila persistente + worker — ortogonal a qualquer framework de orquestração.

Inferência leva de segundos a dezenas de segundos. Um endpoint que segura a
conexão nesse tempo estoura timeout de proxy, perde o trabalho se o cliente
fechar a aba, e impede medir fila separada de inferência.

    POST /jobs      -> enfileira, devolve 202 + job_id
    GET  /jobs/{id} -> QUEUED | PROCESSING | COMPLETED | FAILED
    worker          -> consome a fila e executa

Trocar a fila (SQLite -> Redis) não toca a lógica de negócio.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(slots=True)
class Job:
    id: str
    payload: dict
    status: JobStatus = JobStatus.QUEUED
    created_at: float = 0.0
    attempts: int = 0
    error: str | None = None
    result: dict = field(default_factory=dict)


class JobQueue:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._c() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, error TEXT,
                result TEXT NOT NULL DEFAULT '{}')""")
            c.execute("CREATE INDEX IF NOT EXISTS ix_status ON jobs(status, created_at)")

    def _c(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _row(r: sqlite3.Row) -> Job:
        return Job(r["id"], json.loads(r["payload"]), JobStatus(r["status"]),
                   r["created_at"], r["attempts"], r["error"],
                   json.loads(r["result"] or "{}"))

    def enfileirar(self, payload: dict) -> Job:
        j = Job(uuid.uuid4().hex[:12], payload, created_at=time.time())
        with self._c() as c:
            c.execute("INSERT INTO jobs(id,payload,status,created_at,updated_at)"
                      " VALUES(?,?,?,?,?)",
                      (j.id, json.dumps(payload, ensure_ascii=False),
                       j.status.value, j.created_at, j.created_at))
        return j

    def get(self, job_id: str) -> Job | None:
        with self._c() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row(r) if r else None

    def pendentes(self) -> int:
        with self._c() as c:
            return c.execute("SELECT COUNT(*) FROM jobs WHERE status IN (?,?)",
                             (JobStatus.QUEUED.value, JobStatus.PROCESSING.value)).fetchone()[0]

    def reservar(self) -> Job | None:
        """Reserva atômica: dois workers não pegam o mesmo job."""
        with self._c() as c:
            r = c.execute("SELECT * FROM jobs WHERE status=? ORDER BY created_at LIMIT 1",
                          (JobStatus.QUEUED.value,)).fetchone()
            if not r:
                return None
            ok = c.execute("UPDATE jobs SET status=?, attempts=attempts+1, updated_at=?"
                           " WHERE id=? AND status=?",
                           (JobStatus.PROCESSING.value, time.time(), r["id"],
                            JobStatus.QUEUED.value)).rowcount
            if not ok:
                return None
            r = c.execute("SELECT * FROM jobs WHERE id=?", (r["id"],)).fetchone()
        return self._row(r)

    def concluir(self, job_id: str, status: JobStatus,
                 result: dict | None = None, error: str | None = None) -> None:
        with self._c() as c:
            c.execute("UPDATE jobs SET status=?, result=?, error=?, updated_at=? WHERE id=?",
                      (status.value, json.dumps(result or {}, ensure_ascii=False),
                       error, time.time(), job_id))

    def reconciliar(self) -> int:
        """No boot: jobs presos em PROCESSING (crash) voltam para a fila."""
        with self._c() as c:
            return c.execute("UPDATE jobs SET status=?, updated_at=? WHERE status=?",
                             (JobStatus.QUEUED.value, time.time(),
                              JobStatus.PROCESSING.value)).rowcount


class Worker:
    """Fila serializada. Duas execuções concorrentes no mesmo recurso escasso
    (GPU, cota de API) pioram o p95 das duas."""

    def __init__(self, fila: JobQueue, executor: Callable[[Job], Awaitable[dict]],
                 *, intervalo_s: float = 0.05) -> None:
        self.fila, self.executor, self.intervalo = fila, executor, intervalo_s
        self._task: asyncio.Task | None = None
        self._parar = asyncio.Event()

    async def _loop(self) -> None:
        while not self._parar.is_set():
            job = await asyncio.to_thread(self.fila.reservar)
            if job is None:
                try:
                    await asyncio.wait_for(self._parar.wait(), timeout=self.intervalo)
                except TimeoutError:
                    pass
                continue
            try:
                self.fila.concluir(job.id, JobStatus.COMPLETED, await self.executor(job))
            except Exception as e:                    # nunca derruba o worker
                self.fila.concluir(job.id, JobStatus.FAILED, {}, f"{type(e).__name__}: {e}")

    def start(self) -> None:
        if self._task is None:
            self._parar.clear()
            self._task = asyncio.create_task(self._loop(), name="worker")

    async def stop(self) -> None:
        self._parar.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None
