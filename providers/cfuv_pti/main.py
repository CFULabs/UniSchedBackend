from base.provider import ScheduleProvider
from base.types import Group, Schedule
from .parser import parse_xlsx

from aiohttp import ClientSession
import aiofiles
import aiosqlite
import json
import yaml
import logging
from datetime import datetime
from io import BytesIO
import os


JSON_DIR = "parsed"


class PTIProvider(ScheduleProvider):
    @property
    def description(self) -> str:
        return "Физико-технический институт"

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._base_path = os.path.dirname(__file__)
        with open(os.path.join(self._base_path, "config.yaml")) as f:
            self._config = yaml.safe_load(f)

        self._xlsx_urls = self._config["xlsx_urls"]
        self._study_start = datetime.combine(self._config["study_start_date"], datetime.min.time()).timestamp()
        self._lesson_start_time = self._config["lesson_start_time"]
        self._lesson_length = self._config["lesson_length"]
        self._breaks = self._config["breaks"]

        self._groups: list[Group] = []

    async def on_network_fetch(self, session: ClientSession):
        self._logger.info("Fetching XLSX files...")
        for url in self._xlsx_urls:
            resp = await session.get(url)
            if resp.status != 200:
                self._logger.error(f"[Fetch] Failed to fetch {url}!\nResponse code: {resp.status}")
                continue

            xlsx = await resp.read()
            self._logger.info(f"[Fetch] Parsing {url.rsplit('/', 1)[1]}...")
            try:
                parsed = parse_xlsx(BytesIO(xlsx))
            except ValueError as e:
                self._logger.error(f"[Fetch] Failed to read XLSX from {url}!")
                self._logger.exception(e)
                continue

            # Save parsed schedules
            parsed_dir = os.path.join(self._base_path, JSON_DIR)
            if not os.path.exists(parsed_dir):
                os.mkdir(parsed_dir)

            for group, schedule in parsed.items():
                async with aiofiles.open(os.path.join(parsed_dir, f"{group}.json"), 'w') as f:
                    await f.write(json.dumps(schedule, ensure_ascii=False))

            async with aiosqlite.connect(os.path.join(self._base_path, "mapping.sqlite")) as db:
                # Create table if it doesn't exist
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT
                    )
                    """
                )
                await db.commit()

                cur = await db.execute("SELECT filename FROM groups")
                db_groups = await cur.fetchall()
                await cur.close()
                groups = parsed.keys()

                # Clear removed groups
                for (db_group,) in db_groups:
                    if db_group not in groups:
                        await db.execute(f"DELETE FROM groups WHERE filename='{db_group}'")

                # Fill available groups
                for group in groups:
                    cur = await db.execute(f"SELECT id FROM groups WHERE filename='{group}'")
                    group_id = await cur.fetchone()
                    await cur.close()
                    if group_id is None:
                        # Insert new row
                        await db.execute(f"INSERT INTO groups (filename) VALUES ('{group}')")
                        cur = await db.execute(f"SELECT id FROM groups WHERE filename='{group}'")
                        group_id = await cur.fetchone()
                        await cur.close()

                    self._groups.append(Group(id=group_id[0], name=group))

                await db.commit()

        self._logger.info("[Fetch] Done!")

    @property
    def groups(self) -> list[Group]:
        return self._groups

    async def get_schedule(self, group_id: str | int) -> Schedule:
        group_id = int(group_id)
        group = None
        for g in self._groups:
            if g.id == group_id:
                group = g

        if group is None:
            raise ValueError("This group doesn't exist!")

        # Load schedule for this group
        async with aiofiles.open(os.path.join(self._base_path, JSON_DIR, f"{group.name}.json")) as f:
            weeks = json.loads((await f.read()))

        return Schedule(
            name=group.name,
            study_start_ts=self._study_start,
            lesson_start_time=self._lesson_start_time,
            lesson_length=self._lesson_length,
            breaks=self._breaks,
            has_even_odd=True,
            weeks=weeks
        )
