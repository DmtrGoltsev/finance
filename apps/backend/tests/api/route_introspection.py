from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import NamedTuple

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


class _NestedRoutes(NamedTuple):
    routes: Iterable[object]
    path_prefix: str
    path_format_prefix: str


def _route_path_prefix(route: object) -> tuple[str, str]:
    prefix = getattr(route, "prefix", "") or getattr(route, "path", "") or ""
    path_format_prefix = getattr(route, "path_format", "") or prefix
    if str(path_format_prefix).endswith("/{path}"):
        path_format_prefix = prefix
    return str(prefix), str(path_format_prefix)


def _is_routes_iterable(value: object) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes))


def _nested_route_sources(route: object) -> Sequence[_NestedRoutes]:
    path_prefix, path_format_prefix = _route_path_prefix(route)
    sources: list[_NestedRoutes] = []

    direct_routes = getattr(route, "routes", None)
    if _is_routes_iterable(direct_routes):
        sources.append(
            _NestedRoutes(
                routes=direct_routes,
                path_prefix=path_prefix,
                path_format_prefix=path_format_prefix,
            )
        )

    for nested_container_name in ("app", "router"):
        nested_container = getattr(route, nested_container_name, None)
        nested_routes = getattr(nested_container, "routes", None)
        if _is_routes_iterable(nested_routes):
            sources.append(
                _NestedRoutes(
                    routes=nested_routes,
                    path_prefix=path_prefix,
                    path_format_prefix=path_format_prefix,
                )
            )

    return sources


def iter_api_routes(
    routes: Iterable[object],
    *,
    prefix: str = "",
    path_format_prefix: str | None = None,
    _visited: set[int] | None = None,
) -> Iterator[RuntimeAPIRoute]:
    if path_format_prefix is None:
        path_format_prefix = prefix
    if _visited is None:
        _visited = set()

    for route in routes:
        route_id = id(route)
        if route_id in _visited:
            continue
        _visited.add(route_id)

        if isinstance(route, APIRoute):
            yield RuntimeAPIRoute(
                route=route,
                path=_join_route_paths(prefix, route.path),
                path_format=_join_route_paths(path_format_prefix, route.path_format),
            )
            continue

        for nested_source in _nested_route_sources(route):
            nested_prefix = _join_route_paths(prefix, nested_source.path_prefix)
            nested_path_format_prefix = _join_route_paths(
                path_format_prefix,
                nested_source.path_format_prefix,
            )
            yield from iter_api_routes(
                nested_source.routes,
                prefix=nested_prefix,
                path_format_prefix=nested_path_format_prefix,
                _visited=_visited,
            )
