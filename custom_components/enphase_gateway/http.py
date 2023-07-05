"""Module providing http functions."""

import asyncio
import logging

import httpx


_LOGGER = logging.getLogger(__name__)


async def async_get(url, async_client, retries=2, raise_for_status=True, **kwargs):
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
    for attempt in range(1, retries+2):
        _LOGGER.debug(
            f"HTTP GET Attempt #{attempt}: {url}: kwargs: {kwargs}"
        )
        async with async_client as client:
            try:
                resp = await client.get(url, **kwargs)
                "Response from GET Attempt #{attempt}: {resp}"
                _LOGGER.debug(f"HTTP GET {url}: {resp}: {resp.text}")
                if raise_for_status:
                    resp.raise_for_status()        
            except httpx.TransportError as err:
                if attempt >= retries+2:
                    _LOGGER.debug(
                        f"Transport Error while trying HTTP GET: {url}: {err}"
                    )
                    raise err
                else:
                    await asyncio.sleep(attempt * 0.12)
                    continue
            else:
                _LOGGER.debug(f"Fetched from {url}: {resp}: {resp.text}")
                return resp


async def _async_post(url, async_client, retries=2, raise_for_status=True, **kwargs):
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
    for attempt in range(1, retries+2):
        _LOGGER.debug(
            f"HTTP POST Attempt #{attempt}: {url}: kwargs: {kwargs}"
        )
        async with async_client as client:
            try:
                resp = await client.post(url, **kwargs)
                _LOGGER.debug(f"HTTP POST {url}: {resp}: {resp.text}")
                if raise_for_status:
                    resp.raise_for_status()
            except httpx.TransportError as err:
                if attempt >= retries+2:
                    _LOGGER.debug(
                        f"Transport Error while trying HTTP POST: {url}"
                    )
                    raise err
                else:
                    await asyncio.sleep(attempt * 0.12)
                    continue
            else:
                _LOGGER.debug(f"Fetched from {url}: {resp}: {resp.text}")
                return resp
            
