from unittest.mock import AsyncMock, patch

from app.workers.jobs import process_batch


async def test_process_batch_invokes_pipeline(seed_chat):
    with patch("app.workers.jobs.run_pipeline_for_chat", new=AsyncMock()) as mock_run:
        await process_batch({}, str(seed_chat.id))
        mock_run.assert_awaited_once()
        assert mock_run.call_args.kwargs["chat_id"] == seed_chat.id
