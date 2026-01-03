"""Approval service for managing pending action execution.

This module provides the ApprovalService which handles the approval
lifecycle: validation, execution, and cleanup. This separates execution
coordination from pure session state management.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from ..mcp.executor import ToolExecutor
    from ..mcp.types import ToolResult
    from .session import ChatSession, PendingApproval


class ApprovalService:
    """Handles approval lifecycle: validation, execution, cleanup.

    This service extracts execution coordination from ChatSession,
    keeping session as a pure state container while this class
    handles the execution flow.

    Example:
        >>> service = ApprovalService(session, executor)
        >>> result, approval = await service.execute(approval_id, token)
        >>> service.reject(approval_id, "user cancelled")
    """

    def __init__(self, session: ChatSession, executor: ToolExecutor) -> None:
        """Initialize the approval service.

        Args:
            session: ChatSession for state management.
            executor: ToolExecutor for tool execution.
        """
        self._session = session
        self._executor = executor

    async def execute(
        self,
        approval_id: str,
        token: str,
        modified_params: dict[str, Any] | None = None,
    ) -> tuple[ToolResult, PendingApproval]:
        """Execute an approved action and update session history atomically.

        This method encapsulates the full approval execution lifecycle:
        1. Validates the approval exists and is not expired
        2. Merges any user-modified parameters
        3. Executes the tool via ToolExecutor
        4. Updates the tool message in history with the result
        5. Removes the approval from pending

        Args:
            approval_id: ID of the approval to execute.
            token: Homebox authentication token.
            modified_params: Optional parameters to override the original.

        Returns:
            Tuple of (ToolResult, PendingApproval) - the result and the executed approval.

        Raises:
            ValueError: If approval not found or expired.
        """
        # 1. Validate approval exists and is not expired
        approval = self._session.get_pending_approval(approval_id)
        if not approval:
            raise ValueError(f"Approval not found or expired: {approval_id}")

        # 2. Merge parameters
        final_params = {**approval.parameters}
        if modified_params:
            final_params.update(modified_params)
            logger.info(
                f"User modified parameters for {approval.tool_name}: {modified_params}"
            )

        # 3. Execute the tool
        logger.info(
            f"Executing approved action: {approval.tool_name} with params {final_params}"
        )
        result = await self._executor.execute(approval.tool_name, final_params, token)

        # 4. Update the tool message in history (use tool_call_id directly from approval)
        if approval.tool_call_id:
            result_message = {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "message": (
                    f"Action '{approval.tool_name}' executed successfully."
                    if result.success
                    else f"Action '{approval.tool_name}' failed: {result.error}"
                ),
            }
            self._session.update_tool_message(approval.tool_call_id, json.dumps(result_message))

        # 5. Remove from pending
        self._session.remove_approval(approval_id)

        return result, approval

    def reject(self, approval_id: str, reason: str) -> bool:
        """Reject an approval and update history.

        This is a convenience method that delegates to session.reject_approval.

        Args:
            approval_id: ID of the approval to reject.
            reason: Reason for rejection shown in history.

        Returns:
            True if approval was found and rejected, False otherwise.
        """
        return self._session.reject_approval(approval_id, reason)

    def get_approval(self, approval_id: str) -> PendingApproval | None:
        """Get a pending approval by ID.

        Args:
            approval_id: The approval ID to look up.

        Returns:
            The PendingApproval or None if not found/expired.
        """
        return self._session.get_pending_approval(approval_id)

