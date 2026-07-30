"""Stable MCP 2026-07-28 task status subscriptions."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import anyio
import anyio.streams.memory
from mcp.server.subscriptions import SubscriptionBus
from mcp.shared.exceptions import MCPError
from mcp.shared.subscriptions import (
    SUBSCRIPTION_ID_META_KEY,
    PromptsListChanged,
    ResourcesListChanged,
    ResourceUpdated,
    ServerEvent,
    ToolsListChanged,
    event_matches,
    event_to_notification,
)
from mcp_types import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    Notification,
    NotificationParams,
    SubscriptionFilter,
    SubscriptionsListenRequestParams,
    SubscriptionsListenResult,
)
from pydantic import Field

if TYPE_CHECKING:
    from mcp.server.context import ServerRequestContext

    from .tasks_extension import TasksExtension

TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"
STABLE_PROTOCOL_VERSION = "2026-07-28"
MAX_TASK_IDS_PER_SUBSCRIPTION = 64
MAX_TASK_ID_LENGTH = 128
MAX_TASK_SUBSCRIPTIONS = 1024
MAX_BUFFERED_EVENTS = 128

logger = logging.getLogger(__name__)


class TaskSubscriptionFilter(SubscriptionFilter):
    """Core notification filters plus the SEP-2663 Tasks extension field."""

    task_ids: list[str] | None = Field(
        default=None,
        alias="taskIds",
        max_length=MAX_TASK_IDS_PER_SUBSCRIPTION,
    )


class TaskSubscriptionsListenRequestParams(SubscriptionsListenRequestParams):
    notifications: TaskSubscriptionFilter


class TaskSubscriptionsAcknowledgedParams(NotificationParams):
    notifications: TaskSubscriptionFilter


class TaskSubscriptionsAcknowledgedNotification(
    Notification[
        TaskSubscriptionsAcknowledgedParams,
        Literal["notifications/subscriptions/acknowledged"],
    ]
):
    method: Literal["notifications/subscriptions/acknowledged"] = "notifications/subscriptions/acknowledged"
    params: TaskSubscriptionsAcknowledgedParams


class TaskStatusNotificationParams(NotificationParams):
    """A complete SEP-2663 DetailedTask state, without response resultType."""

    task_id: str = Field(alias="taskId")
    status: Literal["working", "input_required", "completed", "failed", "cancelled"]
    status_message: str | None = Field(default=None, alias="statusMessage")
    created_at: str = Field(alias="createdAt")
    last_updated_at: str = Field(alias="lastUpdatedAt")
    ttl_ms: int | None = Field(alias="ttlMs")
    poll_interval_ms: int = Field(alias="pollIntervalMs")
    result: Any | None = None
    error: dict[str, Any] | None = None
    input_requests: dict[str, Any] | None = Field(default=None, alias="inputRequests")


class TaskStatusNotification(Notification[TaskStatusNotificationParams, Literal["notifications/tasks"]]):
    method: Literal["notifications/tasks"] = "notifications/tasks"
    params: TaskStatusNotificationParams


@dataclass(frozen=True, slots=True)
class TaskStateEvent:
    """Immutable client-visible task state published after durable commit."""

    task_id: str
    owner_digest: str
    snapshot: Mapping[str, Any]


SubscriptionEvent = ServerEvent | TaskStateEvent


def _deduplicate_task_ids(task_ids: list[str] | None) -> tuple[str, ...]:
    if not task_ids:
        return ()
    unique: list[str] = []
    seen: set[str] = set()
    for task_id in task_ids:
        if not isinstance(task_id, str) or not task_id or len(task_id) > MAX_TASK_ID_LENGTH:
            raise MCPError(code=-32602, message="Invalid taskIds")
        if task_id not in seen:
            seen.add(task_id)
            unique.append(task_id)
    return tuple(unique)


def _core_honored(requested: TaskSubscriptionFilter) -> TaskSubscriptionFilter:
    return TaskSubscriptionFilter(
        tools_list_changed=True if requested.tools_list_changed else None,
        prompts_list_changed=True if requested.prompts_list_changed else None,
        resources_list_changed=True if requested.resources_list_changed else None,
        resource_subscriptions=list(requested.resource_subscriptions) if requested.resource_subscriptions else None,
    )


def _has_core_filter(value: TaskSubscriptionFilter) -> bool:
    return bool(
        value.tools_list_changed
        or value.prompts_list_changed
        or value.resources_list_changed
        or value.resource_subscriptions
    )


def _is_core_event(event: SubscriptionEvent) -> bool:
    return isinstance(
        event,
        (ToolsListChanged, PromptsListChanged, ResourcesListChanged, ResourceUpdated),
    )


def _safe_unsubscribe(unsubscribe) -> None:
    try:
        unsubscribe()
    except Exception:
        logger.exception("task subscription unsubscribe raised")


class TaskListenHandler:
    """Serve core and task events on one stable subscriptions/listen stream."""

    def __init__(
        self,
        bus: SubscriptionBus,
        tasks: TasksExtension,
        *,
        max_subscriptions: int = MAX_TASK_SUBSCRIPTIONS,
        max_buffered_events: int = MAX_BUFFERED_EVENTS,
    ):
        self._bus = bus
        self._tasks = tasks
        self._max_subscriptions = max_subscriptions
        self._max_buffered_events = max_buffered_events
        self._streams: set[anyio.streams.memory.MemoryObjectSendStream[SubscriptionEvent]] = set()

    @property
    def active_streams(self) -> int:
        return len(self._streams)

    async def __call__(
        self,
        ctx: ServerRequestContext[Any, Any],
        params: TaskSubscriptionsListenRequestParams,
    ) -> SubscriptionsListenResult:
        if ctx.protocol_version != STABLE_PROTOCOL_VERSION:
            raise MCPError(code=-32601, message="Method not found")
        subscription_id = ctx.request_id
        if subscription_id is None:
            raise MCPError(INVALID_REQUEST, "subscriptions/listen requires a request id")
        if len(self._streams) >= self._max_subscriptions:
            raise MCPError(INTERNAL_ERROR, "Subscription limit reached")

        requested = params.notifications
        requested_task_ids = _deduplicate_task_ids(requested.task_ids)
        if any(not self._tasks.store.valid_task_id(task_id) for task_id in requested_task_ids):
            raise MCPError(code=-32602, message="Invalid taskIds")
        if requested.task_ids is not None:
            self._tasks.require_capability(ctx)

        honored = _core_honored(requested)
        honored_uris = frozenset(honored.resource_subscriptions or ())
        owner_digest = self._tasks.principal_digest()
        accepted_task_ids: set[str] = set()
        meta: dict[str, Any] = {SUBSCRIPTION_ID_META_KEY: subscription_id}

        send, recv = anyio.create_memory_object_stream[SubscriptionEvent](self._max_buffered_events)

        def deliver(event: SubscriptionEvent) -> None:
            matches = False
            if isinstance(event, TaskStateEvent):
                matches = event.owner_digest == owner_digest and event.task_id in accepted_task_ids
            elif _is_core_event(event):
                matches = event_matches(honored, honored_uris, event)
            if not matches:
                return
            try:
                send.send_nowait(event)
            except anyio.ClosedResourceError:
                pass
            except anyio.WouldBlock:
                logger.warning("task listen stream %r backlog full; ending stream", subscription_id)
                self._streams.discard(send)
                send.close()

        # Register before capturing current state so a transition cannot fall
        # between the snapshot and the live stream.
        unsubscribe = self._bus.subscribe(deliver)
        self._streams.add(send)
        try:
            records = self._tasks.subscription_records(requested_task_ids)
            accepted_order = tuple(record.task_id for record in records)
            accepted_task_ids.update(accepted_order)
            honored.task_ids = list(accepted_order) or None

            await ctx.session.send_notification(
                TaskSubscriptionsAcknowledgedNotification(
                    params=TaskSubscriptionsAcknowledgedParams(
                        notifications=honored,
                        _meta=meta,
                    )
                ),
                related_request_id=subscription_id,
            )

            for record in records:
                await self._send_task(ctx, meta, record.to_notification())

            if not accepted_task_ids and not _has_core_filter(honored):
                return SubscriptionsListenResult(_meta=meta)

            async for event in recv:
                if isinstance(event, TaskStateEvent):
                    await self._send_task(ctx, meta, event.snapshot)
                else:
                    await ctx.session.send_notification(
                        event_to_notification(event, meta),
                        related_request_id=subscription_id,
                    )
        finally:
            _safe_unsubscribe(unsubscribe)
            self._streams.discard(send)
            send.close()
            recv.close()
        return SubscriptionsListenResult(_meta=meta)

    @staticmethod
    async def _send_task(ctx, meta: dict[str, Any], snapshot: Mapping[str, Any]) -> None:
        payload = dict(snapshot)
        payload["_meta"] = meta
        await ctx.session.send_notification(
            TaskStatusNotification(params=TaskStatusNotificationParams.model_validate(payload)),
            related_request_id=ctx.request_id,
        )

    def close(self) -> None:
        for stream in list(self._streams):
            stream.close()
