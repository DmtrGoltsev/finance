from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from fastapi.routing import APIRoute

try:
    from fastapi.routing import iter_route_contexts as _fastapi_iter_route_contexts
except ImportError:  # pragma: no cover - exercised under older FastAPI pins.
    _fastapi_iter_route_contexts = None


@dataclass(frozen=True)
class RuntimeAPIRoute:
    route: APIRoute
    path: str
    path_format: str
    include_in_schema: bool
    methods: set[str] | None

    @property
    def original_route(self) -> APIRoute:
        return self.route


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
    return _nested_route_sources_with_prefix(route, path_prefix, path_format_prefix)


def _nested_route_sources_with_prefix(
    route: object,
    path_prefix: str,
    path_format_prefix: str,
) -> Sequence[_NestedRoutes]:
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


def _runtime_route_from_context(route_context: object) -> RuntimeAPIRoute | None:
    original_route = getattr(route_context, "original_route", None)
    if not isinstance(original_route, APIRoute):
        return None

    path = getattr(route_context, "path", None)
    path_format = getattr(route_context, "path_format", None)
    if path is None or path_format is None:
        return None

    return RuntimeAPIRoute(
        route=original_route,
        path=str(path),
        path_format=str(path_format),
        include_in_schema=bool(getattr(route_context, "include_in_schema", False)),
        methods=getattr(route_context, "methods", None),
    )


def _iter_api_routes_from_contexts(
    routes: list[object],
    *,
    iter_route_contexts: Callable[[Sequence[object]], Iterable[object]],
    prefix: str,
    path_format_prefix: str,
    _visited: set[int],
) -> Iterator[RuntimeAPIRoute]:
    route_contexts = list(iter_route_contexts(routes))
    if not route_contexts:
        return

    for route_context in route_contexts:
        runtime_route = _runtime_route_from_context(route_context)
        if runtime_route is not None:
            yield runtime_route
            continue

        route = getattr(route_context, "route", None)
        if route is None:
            route = getattr(route_context, "original_route", None)
        if route is None:
            continue

        route_id = id(route)
        if route_id in _visited:
            continue
        _visited.add(route_id)

        context_path = getattr(route_context, "path", None)
        context_path_format = getattr(route_context, "path_format", None)
        if context_path is not None:
            nested_prefix_base = _join_route_paths(prefix, str(context_path))
        else:
            nested_prefix_base = _join_route_paths(prefix, _route_path_prefix(route)[0])
        if context_path_format is not None:
            nested_path_format_base = _join_route_paths(
                path_format_prefix,
                str(context_path_format),
            )
        else:
            nested_path_format_base = _join_route_paths(
                path_format_prefix,
                _route_path_prefix(route)[1],
            )

        for nested_source in _nested_route_sources_with_prefix(
            route,
            nested_prefix_base,
            nested_path_format_base,
        ):
            yield from iter_api_routes(
                nested_source.routes,
                prefix=nested_source.path_prefix,
                path_format_prefix=nested_source.path_format_prefix,
                _visited=_visited,
            )


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

    route_list = list(routes)
    if _fastapi_iter_route_contexts is not None:
        yield from _iter_api_routes_from_contexts(
            route_list,
            iter_route_contexts=_fastapi_iter_route_contexts,
            prefix=prefix,
            path_format_prefix=path_format_prefix,
            _visited=_visited,
        )
        return

    for route in route_list:
        route_id = id(route)
        if route_id in _visited:
            continue
        _visited.add(route_id)

        if isinstance(route, APIRoute):
            yield RuntimeAPIRoute(
                route=route,
                path=_join_route_paths(prefix, route.path),
                path_format=_join_route_paths(path_format_prefix, route.path_format),
                include_in_schema=route.include_in_schema,
                methods=route.methods,
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
