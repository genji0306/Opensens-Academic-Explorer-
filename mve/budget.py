"""Offline WP-9a accounting primitives; this module contains no model transport.

One campaign uses one SQLite file for every wave. The window below reproduces the
borrowed runner's UTC policy; vendor agreement remains a WP-0b prerequisite.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

from mve.money import BudgetError as BudgetError, microdollars as microdollars
from mve.pricing import normalize_prices, token_ceiling

WINDOW_POLICY = "borrowed-runner-20260917:UTC:Mon-Fri:01-04,06-10:UNVERIFIED"


def offpeak(when):
    if when.tzinfo is None or when.utcoffset() is None:
        raise BudgetError("timezone-aware clock required")
    utc = when.astimezone(timezone.utc)
    return utc.weekday() >= 5 or not (1 <= utc.hour < 4 or 6 <= utc.hour < 10)


def checked_time(when=None):
    when = when or datetime.now(timezone.utc)
    if not offpeak(when):
        raise BudgetError("peak-hour dispatch refused")
    return when.astimezone(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", value):
        raise BudgetError("invalid attempt, wave or provider identifier")
    return value


class BudgetLedger:
    def __init__(self, path, *, aggregate="20", p0="2", p1="8", price_table=None):
        self.path = Path(path).resolve()
        caps = {
            "aggregate": microdollars(aggregate),
            "P0": microdollars(p0),
            "P1": microdollars(p1),
        }
        if not (
            0 < caps["aggregate"] <= 20_000_000
            and 0 < caps["P0"] <= 2_000_000
            and 0 < caps["P1"] <= 8_000_000
        ):
            raise BudgetError("caps exceed D4 or are empty")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize(
            caps, normalize_prices({} if price_table is None else price_table)
        )

    @contextmanager
    def _transaction(self):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _initialize(self, caps, prices):
        configuration = json.dumps(
            {"caps": caps, "window": WINDOW_POLICY, "prices": prices}, sort_keys=True
        )
        with self._transaction() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, phase TEXT NOT NULL, wave TEXT NOT NULL, reserved INTEGER NOT NULL, actual INTEGER, state TEXT NOT NULL, created TEXT NOT NULL, dispatched TEXT, receipt TEXT)"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS quota (id TEXT PRIMARY KEY, provider TEXT NOT NULL, units INTEGER NOT NULL)"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, detail TEXT NOT NULL, created TEXT NOT NULL)"
            )
            existing = con.execute(
                "SELECT value FROM metadata WHERE key=?", ("configuration",)
            ).fetchone()
            if existing and existing["value"] != configuration:
                raise BudgetError("cannot change campaign caps or window on resume")
            con.execute(
                "INSERT OR IGNORE INTO metadata VALUES (?,?)",
                ("configuration", configuration),
            )
            con.execute("INSERT OR IGNORE INTO metadata VALUES (?,?)", ("frozen", "0"))

    @staticmethod
    def _frozen(con):
        return (
            con.execute(
                "SELECT value FROM metadata WHERE key=?", ("frozen",)
            ).fetchone()["value"]
            == "1"
        )

    @staticmethod
    def _exposure(con, phase=None):
        query = "SELECT COALESCE(SUM(CASE WHEN state='settled' THEN actual ELSE reserved END),0) AS total FROM attempts WHERE state!='cancelled'"
        args = ()
        if phase is not None:
            query += " AND phase=?"
            args = (phase,)
        return con.execute(query, args).fetchone()["total"]

    @staticmethod
    def _attempt(con, attempt):
        row = con.execute("SELECT * FROM attempts WHERE id=?", (attempt,)).fetchone()
        if row is None:
            raise BudgetError("unknown attempt")
        return row

    def reserve(self, attempt, phase, ceiling, *, wave, when=None):
        identifier(attempt)
        identifier(wave)
        if phase not in ("P0", "P1", "P2"):
            raise BudgetError("D4 authorizes P0-P2 only")
        amount = microdollars(ceiling)
        if amount <= 0:
            raise BudgetError("reservation must be positive")
        with self._transaction() as con:
            timestamp = checked_time(when)
            if self._frozen(con):
                raise BudgetError("campaign frozen")
            caps = json.loads(
                con.execute(
                    "SELECT value FROM metadata WHERE key=?", ("configuration",)
                ).fetchone()["value"]
            )["caps"]
            if con.execute("SELECT 1 FROM attempts WHERE id=?", (attempt,)).fetchone():
                raise BudgetError("attempt already exists; never dispatch twice")
            if self._exposure(con) + amount > caps["aggregate"]:
                raise BudgetError(
                    "aggregate cap including in-flight reservations exceeded"
                )
            if phase in caps and self._exposure(con, phase) + amount > caps[phase]:
                raise BudgetError("phase cap including in-flight reservations exceeded")
            con.execute(
                "INSERT INTO attempts(id,phase,wave,reserved,state,created) VALUES (?,?,?,?,?,?)",
                (attempt, phase, wave, amount, "reserved", timestamp),
            )
        return amount

    def reserve_tokens(
        self, attempt, phase, model, *, input_tokens, output_tokens, wave, when=None
    ):
        """Reserve a positive paid-call ceiling; zero-token/zero-rate bounds are refused."""
        prices = self.snapshot()["configuration"]["prices"]
        amount = token_ceiling(
            prices, model, input_tokens=input_tokens, output_tokens=output_tokens
        )
        ceiling = f"{amount // 1_000_000}.{amount % 1_000_000:06d}"
        return self.reserve(attempt, phase, ceiling, wave=wave, when=when)

    def mark_dispatched(self, attempt, *, when=None):
        with self._transaction() as con:
            timestamp = checked_time(when)
            if self._frozen(con):
                raise BudgetError("campaign frozen")
            if self._attempt(con, attempt)["state"] != "reserved":
                raise BudgetError("dispatch permit already used or cancelled")
            con.execute(
                "UPDATE attempts SET state=?,dispatched=? WHERE id=?",
                ("dispatched", timestamp, attempt),
            )
        # Durable intent exists before transport; any crash keeps the full reservation.

    def cancel_unsent(self, attempt):
        with self._transaction() as con:
            if self._attempt(con, attempt)["state"] != "reserved":
                raise BudgetError("only never-dispatched reservations may be cancelled")
            con.execute(
                "UPDATE attempts SET state=? WHERE id=?", ("cancelled", attempt)
            )

    def reconcile(self, attempt, actual, *, receipt_sha256):
        amount = microdollars(actual)
        if not isinstance(receipt_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", receipt_sha256
        ):
            raise BudgetError("receipt hash required")
        with self._transaction() as con:
            row = self._attempt(con, attempt)
            if row["state"] != "dispatched":
                raise BudgetError("only dispatched attempts can settle once")
            con.execute(
                "UPDATE attempts SET state=?,actual=?,receipt=? WHERE id=?",
                ("settled", amount, receipt_sha256, attempt),
            )
            if amount > row["reserved"]:
                con.execute("UPDATE metadata SET value=? WHERE key=?", ("1", "frozen"))
                self._event(con, "accounting_breach", attempt)
        # Overcharges remain in the ledger even when they exceed the original bound.

    @staticmethod
    def _event(con, kind, detail):
        con.execute(
            "INSERT INTO events(kind,detail,created) VALUES (?,?,?)",
            (kind, detail, datetime.now(timezone.utc).isoformat()),
        )

    def stop(self, reason):
        if reason not in {"mechanical_failure", "zero_measurements", "operator_stop"}:
            raise BudgetError("unknown stop reason")
        with self._transaction() as con:
            con.execute("UPDATE metadata SET value=? WHERE key=?", ("1", "frozen"))
            self._event(con, "stop", reason)

    def resume(self, *, actor):
        # Role assertion only: the future operator adapter authenticates the caller.
        if actor != "Opus":
            raise BudgetError("restart authority is Opus")
        with self._transaction() as con:
            if not self._frozen(con):
                raise BudgetError("campaign is not stopped")
            if con.execute(
                "SELECT 1 FROM attempts WHERE state='dispatched'"
            ).fetchone():
                raise BudgetError("reconcile all uncertain dispatched attempts first")
            caps = json.loads(
                con.execute(
                    "SELECT value FROM metadata WHERE key='configuration'"
                ).fetchone()["value"]
            )["caps"]
            if self._exposure(con) > caps["aggregate"] or any(
                self._exposure(con, phase) > caps[phase] for phase in ("P0", "P1")
            ):
                raise BudgetError("recorded exposure exceeds campaign caps")
            con.execute("UPDATE metadata SET value=? WHERE key=?", ("0", "frozen"))
            self._event(con, "resume", actor)

    def record_quota(self, entry, *, provider, units):
        identifier(entry)
        identifier(provider)
        if type(units) is not int or units <= 0:
            raise BudgetError("quota units must be positive integers")
        with self._transaction() as con:
            if con.execute("SELECT 1 FROM quota WHERE id=?", (entry,)).fetchone():
                raise BudgetError("quota entry already exists")
            con.execute("INSERT INTO quota VALUES (?,?,?)", (entry, provider, units))

    def snapshot(self):
        with self._transaction() as con:
            return {
                "exposure_micro_usd": self._exposure(con),
                "frozen": self._frozen(con),
                "configuration": json.loads(
                    con.execute(
                        "SELECT value FROM metadata WHERE key=?", ("configuration",)
                    ).fetchone()["value"]
                ),
                "attempts": [
                    dict(row)
                    for row in con.execute("SELECT * FROM attempts ORDER BY id")
                ],
                "events": [
                    dict(row) for row in con.execute("SELECT * FROM events ORDER BY id")
                ],
                "quota": [
                    dict(row) for row in con.execute("SELECT * FROM quota ORDER BY id")
                ],
            }
