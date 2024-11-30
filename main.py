from fastapi import FastAPI, Path
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
import aiohttp
import asyncio
import logging
from typing import Annotated
from enum import Enum

from base.types import Group, Schedule
from providers.cfuv_pti import PTIProvider


class ProviderInfo(BaseModel):
    name: str
    description: str


class Errors(str, Enum):
    invalid_provider = "invalid_provider"
    invalid_group = "invalid_group"


class ErrorResponse(BaseModel):
    error: Errors
    message: str


ProviderPathParam = Annotated[str, Path(title="Provider name", description="Can be retrieved from /providers")]

PROVIDERS = {
    "cfuv_pti": PTIProvider()
}


# Prepare providers
async def fetch_schedules():
    async with aiohttp.ClientSession() as session:
        providers = PROVIDERS.values()
        # Launch fetching concurrently
        await asyncio.gather(*[p.on_network_fetch(session) for p in providers])


@asynccontextmanager
async def lifespan(_):
    await fetch_schedules()
    yield


logging.basicConfig(level=logging.INFO)
app = FastAPI(lifespan=lifespan)


def get_provider(name: str):
    provider = PROVIDERS.get(name)
    if not provider:
        raise HTTPException(
            status_code=400,
            detail={"error": Errors.invalid_provider, "message": "Invalid provider name"}
        )

    return provider


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_, exc):
    return JSONResponse(exc.detail, status_code=exc.status_code)


@app.get("/providers", response_model=list[ProviderInfo])
async def get_providers():
    return [ProviderInfo(name=name, description=obj.description) for name, obj in PROVIDERS.items()]


@app.get("/{provider_name}/groups", response_model=list[Group], responses={400: {"model": ErrorResponse}})
async def get_groups(
    provider_name: ProviderPathParam
):
    return get_provider(provider_name).groups


@app.get(
    "/{provider_name}/{group_id}/schedule",
    response_model=Schedule,
    response_model_exclude_none=True,
    responses={400: {"model": ErrorResponse}}
)
async def get_schedule(
    provider_name: ProviderPathParam,
    group_id: Annotated[int | str, Path(title="Group ID")]
):
    try:
        return await (get_provider(provider_name).get_schedule(group_id))
    except ValueError as e:
        if type(e) is not ValueError:
            raise

        raise HTTPException(
            status_code=400,
            detail={"error": Errors.invalid_group, "message": "This group doesn't exist"}
        )
