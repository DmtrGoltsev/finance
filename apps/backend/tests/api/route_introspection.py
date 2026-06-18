from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from fastapi.routing import APIRoute


@dataclass(frozen=True)
class RuntimeAPIRoute:
    route: APIRoute
    path: str
    path_format: str

    @property
    def include_in_schema(self) -> bool:
        return self.route.include_in_schema

    @property
    def methods(self) -> set[str] | None:
        return self.route.methods


def _join_route_paths(prefix: str, path: str) -> str:
    if not prefix:
        return path
    if not path:
        return prefix

    normalized_prefix = prefix.rstrip("/")
    if path == normalized_prefix or path.startswith(f"{normalized_prefix}/"):
        return path

    return f"{normalized_prefix}/{path.lstrip('/')}"


def iter_api_routes(
    routes: Iterable[object],
    *,
    prefix: str = "",
) -> Iterator[RuntimeAPIRoute]:
    for route in routes:
        if isinstance(route, APIRoute):
            yield RuntimeAPIRoute(
                route=route,
                path=_join_route_paths(prefix, route.path),
                path_format=_join_route_paths(prefix, route.path_format),
            )
            continue

        nested_routes = getattr(route, "routes", None)
        if nested_routes is not None:
            nested_prefix = _join_route_paths(prefix, getattr(route, "prefix", ""))
            yield from iter_api_routes(nested_routes, prefix=nested_prefix)
