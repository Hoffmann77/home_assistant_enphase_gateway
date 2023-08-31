"""Async http methods."""

import asyncio
import logging

import httpx


_LOGGER = logging.getLogger(__name__)


async def async_get(
    async_client: httpx.AsyncClient,
    url: str,
    retries: int = 2,
    raise_for_status: bool = True,
    **kwargs
    ):
    """Send a HTTP GET request using httpx.
    
    Parameters
    ----------
    url : str
        Target url.
    async_client : httpx.AsyncClient
        Async client.
    retries : int, optional
        Number of reties in case of a transport error. The default is 2.
    raise_for_status : bool, optional
        If True call raise_for_status on the response. The default is True.
    **kwargs : dict, optional
        Extra arguments for httpx.AsyncClient.get(**kwargs).

    Raises
    ------
    err : httpx.TransportError
        Transport error.

    Returns
    -------
    resp : httpx.Response
        HTTP GET response.

    """
    #async with async_client as client:
    for attempt in range(1, retries+2):
        _LOGGER.debug(
            f"HTTP GET Attempt #{attempt}: {url}: kwargs: {kwargs}"
        )
        try:
            resp = await async_client.get(url, **kwargs)
            _LOGGER.debug(
                f"Response: HTTP GET #{attempt}: {resp}: {resp.text}")
            if raise_for_status:
                resp.raise_for_status()
        except httpx.TransportError as err:
            if attempt >= retries+1:
                _LOGGER.debug(
                    f"Transport Error: HTTP GET Attempt #{attempt}: {err}"
                )
                raise err
            else:
                await asyncio.sleep(attempt * 0.10)
                continue
        else:
            _LOGGER.debug(f"Success: HTTP GET Attempt #{attempt}")
            return resp


async def async_post(async_client, url, retries=2, raise_for_status=True, **kwargs):
    """Send a HTTP POST request using httpx.
    
    Parameters
    ----------
    url : str
        Target url.
    async_client : httpx.AsyncClient
        Async client.
    retries : int, optional
        Number of reties in case of a transport error. The default is 2.
    raise_for_status : bool, optional
        If True call raise_for_status on the response. The default is True.
    **kwargs : dict, optional
        Extra arguments for httpx.AsyncClient.get(**kwargs).

    Returns
    -------
    resp : HTTP response
        httpx response object.

    """
    #async with async_client as client:
    for attempt in range(1, retries+2):
        _LOGGER.debug(
            f"HTTP POST Attempt #{attempt}: {url}: kwargs: {kwargs}"
        )
        try:
            resp = await async_client.post(url, **kwargs)
            _LOGGER.debug(
                f"Response: HTTP POST #{attempt}: {resp}: {resp.text}"
            )
            if raise_for_status:
                resp.raise_for_status()
        except httpx.TransportError as err:
            if attempt >= retries+1:
                _LOGGER.debug(
                    f"Transport Error: HTTP POST Attempt #{attempt}: {err}"
                )
                raise err
            else:
                await asyncio.sleep(attempt * 0.10)
                continue
        else:
            _LOGGER.debug(f"Success: HTTP POST Attempt #{attempt}")
            return resp

