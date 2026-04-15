"""Tests for the GithubManager class.

Covers:
- User not found scenario when a GitHub user hasn't created an OpenHands account
- Sign-up message posting to GitHub issues/PRs
- All supported trigger types: labeled issues, issue comments, PR comments, inline PR comments
- Laminar observability integration
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from integrations.github.github_manager import GithubManager
from integrations.models import Message, SourceType
from integrations.utils import HOST_URL, get_user_not_found_message


class TestGithubManagerUserNotFound:
    """Test cases for when a valid GitHub user hasn't created an OpenHands account."""

    @pytest.fixture
    def mock_token_manager(self):
        """Create a mock token manager."""
        token_manager = MagicMock()
        token_manager.get_user_id_from_idp_user_id = AsyncMock(return_value=None)
        return token_manager

    @pytest.fixture
    def mock_data_collector(self):
        """Create a mock data collector."""
        data_collector = MagicMock()
        data_collector.process_payload = AsyncMock()
        return data_collector

    @pytest.fixture
    def github_issue_comment_message(self):
        """Create a sample GitHub issue comment message with an @openhands mention."""
        return Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'action': 'created',
                    'sender': {
                        'id': 67890,
                        'login': 'testuser',
                    },
                    'repository': {
                        'owner': {'login': 'test-owner'},
                        'name': 'test-repo',
                    },
                    'issue': {
                        'number': 42,
                    },
                    'comment': {
                        'body': '@openhands please help with this issue',
                    },
                },
            },
        )

    # Alias for backward compatibility with existing tests
    @pytest.fixture
    def github_issue_message(self, github_issue_comment_message):
        """Alias for github_issue_comment_message for backward compatibility."""
        return github_issue_comment_message

    @pytest.fixture
    def github_labeled_issue_message(self):
        """Create a sample GitHub labeled issue message (when openhands label is added)."""
        return Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'action': 'labeled',
                    'sender': {
                        'id': 67890,
                        'login': 'labeluser',
                    },
                    'repository': {
                        'owner': {'login': 'test-owner'},
                        'name': 'test-repo',
                    },
                    'issue': {
                        'number': 55,
                    },
                    'label': {
                        'name': 'openhands',
                    },
                },
            },
        )

    @pytest.fixture
    def github_pr_comment_message(self):
        """Create a sample GitHub PR comment message (comment on a PR, accessed via issue endpoint)."""
        return Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'action': 'created',
                    'sender': {
                        'id': 67890,
                        'login': 'prcommentuser',
                    },
                    'repository': {
                        'owner': {'login': 'test-owner'},
                        'name': 'test-repo',
                    },
                    'issue': {
                        'number': 77,
                        'pull_request': {
                            'url': 'https://api.github.com/repos/test-owner/test-repo/pulls/77',
                        },
                    },
                    'comment': {
                        'body': '@openhands please review this PR',
                    },
                },
            },
        )

    @pytest.fixture
    def github_inline_pr_comment_message(self):
        """Create a sample GitHub inline PR review comment message."""
        return Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'action': 'created',
                    'sender': {
                        'id': 67890,
                        'login': 'inlineuser',
                    },
                    'repository': {
                        'owner': {'login': 'test-owner'},
                        'name': 'test-repo',
                    },
                    'pull_request': {
                        'number': 100,
                        'head': {
                            'ref': 'feature-branch',
                        },
                    },
                    'comment': {
                        'id': 12345,
                        'node_id': 'PRRC_abc123',
                        'body': '@openhands fix this code',
                        'path': 'src/main.py',
                        'line': 42,
                    },
                },
            },
        )

    # Alias for backward compatibility
    @pytest.fixture
    def github_pr_message(self, github_inline_pr_comment_message):
        """Alias for github_inline_pr_comment_message for backward compatibility."""
        return github_inline_pr_comment_message

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    @patch('integrations.github.github_manager.Github')
    def test_send_user_not_found_message_for_issue(
        self,
        mock_github_class,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
        github_issue_message,
    ):
        """Test that a sign-up message is sent when a valid user hasn't created an OpenHands account on an issue."""
        # Set up mocks
        mock_github_instance = MagicMock()
        mock_github_class.return_value.__enter__ = MagicMock(
            return_value=mock_github_instance
        )
        mock_github_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        mock_integration_instance = MagicMock()
        mock_github_integration.return_value = mock_integration_instance
        mock_integration_instance.get_access_token.return_value = MagicMock(
            token='fake-token'
        )

        # Create manager and call the method
        manager = GithubManager(mock_token_manager, mock_data_collector)

        manager._send_user_not_found_message(github_issue_message, 'testuser')

        # Verify the comment was posted
        mock_github_instance.get_repo.assert_called_once_with('test-owner/test-repo')
        mock_repo.get_issue.assert_called_once_with(number=42)

        # Verify the comment contains the expected sign-up message
        mock_issue.create_comment.assert_called_once()
        comment_text = mock_issue.create_comment.call_args[0][0]
        assert '@testuser' in comment_text
        assert "haven't created an OpenHands account" in comment_text
        assert 'sign up' in comment_text.lower()
        assert HOST_URL in comment_text

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    @patch('integrations.github.github_manager.Github')
    def test_send_user_not_found_message_for_pr(
        self,
        mock_github_class,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
        github_pr_message,
    ):
        """Test that a sign-up message is sent when a valid user hasn't created an OpenHands account on a PR."""
        # Set up mocks
        mock_github_instance = MagicMock()
        mock_github_class.return_value.__enter__ = MagicMock(
            return_value=mock_github_instance
        )
        mock_github_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        mock_integration_instance = MagicMock()
        mock_github_integration.return_value = mock_integration_instance
        mock_integration_instance.get_access_token.return_value = MagicMock(
            token='fake-token'
        )

        # Create manager and call the method
        manager = GithubManager(mock_token_manager, mock_data_collector)

        manager._send_user_not_found_message(github_pr_message, 'pruser')

        # Verify the comment was posted with PR number
        mock_github_instance.get_repo.assert_called_once_with('test-owner/test-repo')
        mock_repo.get_issue.assert_called_once_with(number=100)

        # Verify the comment contains the expected sign-up message
        mock_issue.create_comment.assert_called_once()
        comment_text = mock_issue.create_comment.call_args[0][0]
        assert '@pruser' in comment_text
        assert "haven't created an OpenHands account" in comment_text

    @pytest.mark.asyncio
    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    @patch('integrations.github.github_manager.Github')
    async def test_receive_message_sends_user_not_found_when_keycloak_user_id_is_none(
        self,
        mock_github_class,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
        github_issue_message,
    ):
        """Test that receive_message sends a sign-up message when get_user_id_from_idp_user_id returns None."""
        # Set up mocks
        mock_github_instance = MagicMock()
        mock_github_class.return_value.__enter__ = MagicMock(
            return_value=mock_github_instance
        )
        mock_github_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        mock_integration_instance = MagicMock()
        mock_github_integration.return_value = mock_integration_instance
        mock_integration_instance.get_access_token.return_value = MagicMock(
            token='fake-token'
        )
        mock_integration_instance.get_github_for_installation.return_value.__enter__ = (
            MagicMock(return_value=mock_github_instance)
        )
        mock_integration_instance.get_github_for_installation.return_value.__exit__ = (
            MagicMock(return_value=False)
        )

        # Mock user having write access (so is_job_requested returns True)
        mock_repo.get_collaborator_permission.return_value = 'write'

        # Token manager returns None for keycloak_user_id (user hasn't created an account)
        mock_token_manager.get_user_id_from_idp_user_id = AsyncMock(return_value=None)

        # Create manager
        manager = GithubManager(mock_token_manager, mock_data_collector)

        # Call receive_message
        await manager.receive_message(github_issue_message)

        # Verify get_user_id_from_idp_user_id was called
        mock_token_manager.get_user_id_from_idp_user_id.assert_called_once()

        # Verify the sign-up message was posted
        mock_issue.create_comment.assert_called_once()
        comment_text = mock_issue.create_comment.call_args[0][0]
        assert '@testuser' in comment_text
        assert "haven't created an OpenHands account" in comment_text
        assert 'sign up' in comment_text.lower()

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    @patch('integrations.github.github_manager.logger')
    def test_send_user_not_found_message_logs_warning_when_no_issue_number(
        self,
        mock_logger,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
    ):
        """Test that a warning is logged when issue/PR number cannot be determined."""
        mock_integration_instance = MagicMock()
        mock_github_integration.return_value = mock_integration_instance
        mock_integration_instance.get_access_token.return_value = MagicMock(
            token='fake-token'
        )

        # Create a message without issue or pull_request
        message_without_issue = Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'action': 'created',
                    'sender': {
                        'id': 67890,
                        'login': 'testuser',
                    },
                    'repository': {
                        'owner': {'login': 'test-owner'},
                        'name': 'test-repo',
                    },
                },
            },
        )

        manager = GithubManager(mock_token_manager, mock_data_collector)

        manager._send_user_not_found_message(message_without_issue, 'testuser')

        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        assert 'Could not determine issue/PR number' in str(
            mock_logger.warning.call_args
        )

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    @patch('integrations.github.github_manager.Github')
    def test_send_user_not_found_message_for_labeled_issue(
        self,
        mock_github_class,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
        github_labeled_issue_message,
    ):
        """Test that a sign-up message is sent for labeled issue events."""
        # Set up mocks
        mock_github_instance = MagicMock()
        mock_github_class.return_value.__enter__ = MagicMock(
            return_value=mock_github_instance
        )
        mock_github_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        mock_integration_instance = MagicMock()
        mock_github_integration.return_value = mock_integration_instance
        mock_integration_instance.get_access_token.return_value = MagicMock(
            token='fake-token'
        )

        # Create manager and call the method
        manager = GithubManager(mock_token_manager, mock_data_collector)

        manager._send_user_not_found_message(github_labeled_issue_message, 'labeluser')

        # Verify the comment was posted with correct issue number
        mock_github_instance.get_repo.assert_called_once_with('test-owner/test-repo')
        mock_repo.get_issue.assert_called_once_with(number=55)

        # Verify the comment contains the expected sign-up message
        mock_issue.create_comment.assert_called_once()
        comment_text = mock_issue.create_comment.call_args[0][0]
        assert '@labeluser' in comment_text
        assert "haven't created an OpenHands account" in comment_text
        assert 'sign up' in comment_text.lower()

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    @patch('integrations.github.github_manager.Github')
    def test_send_user_not_found_message_for_pr_comment_via_issue_endpoint(
        self,
        mock_github_class,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
        github_pr_comment_message,
    ):
        """Test that a sign-up message is sent for PR comments (accessed via issue endpoint)."""
        # Set up mocks
        mock_github_instance = MagicMock()
        mock_github_class.return_value.__enter__ = MagicMock(
            return_value=mock_github_instance
        )
        mock_github_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        mock_integration_instance = MagicMock()
        mock_github_integration.return_value = mock_integration_instance
        mock_integration_instance.get_access_token.return_value = MagicMock(
            token='fake-token'
        )

        # Create manager and call the method
        manager = GithubManager(mock_token_manager, mock_data_collector)

        manager._send_user_not_found_message(github_pr_comment_message, 'prcommentuser')

        # Verify the comment was posted with correct PR number (from issue.number)
        mock_github_instance.get_repo.assert_called_once_with('test-owner/test-repo')
        mock_repo.get_issue.assert_called_once_with(number=77)

        # Verify the comment contains the expected sign-up message
        mock_issue.create_comment.assert_called_once()
        comment_text = mock_issue.create_comment.call_args[0][0]
        assert '@prcommentuser' in comment_text
        assert "haven't created an OpenHands account" in comment_text
        assert 'sign up' in comment_text.lower()


class TestGetIssueNumberFromPayload:
    """Test cases for the _get_issue_number_from_payload helper method."""

    @pytest.fixture
    def mock_token_manager(self):
        """Create a mock token manager."""
        token_manager = MagicMock()
        return token_manager

    @pytest.fixture
    def mock_data_collector(self):
        """Create a mock data collector."""
        data_collector = MagicMock()
        return data_collector

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    def test_extracts_issue_number_from_issue_payload(
        self,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
    ):
        """Test extraction from payload with 'issue' key (labeled issues, issue comments, PR comments)."""
        message = Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'issue': {'number': 42},
                    'repository': {'owner': {'login': 'owner'}, 'name': 'repo'},
                },
            },
        )

        manager = GithubManager(mock_token_manager, mock_data_collector)
        result = manager._get_issue_number_from_payload(message)

        assert result == 42

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    def test_extracts_pr_number_from_pull_request_payload(
        self,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
    ):
        """Test extraction from payload with 'pull_request' key (inline PR comments)."""
        message = Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'pull_request': {'number': 100},
                    'repository': {'owner': {'login': 'owner'}, 'name': 'repo'},
                },
            },
        )

        manager = GithubManager(mock_token_manager, mock_data_collector)
        result = manager._get_issue_number_from_payload(message)

        assert result == 100

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    def test_prefers_issue_over_pull_request_when_both_present(
        self,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
    ):
        """Test that issue takes precedence over pull_request (edge case)."""
        message = Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'issue': {'number': 42},
                    'pull_request': {'number': 100},
                    'repository': {'owner': {'login': 'owner'}, 'name': 'repo'},
                },
            },
        )

        manager = GithubManager(mock_token_manager, mock_data_collector)
        result = manager._get_issue_number_from_payload(message)

        assert result == 42

    @patch('integrations.github.github_manager.Auth')
    @patch('integrations.github.github_manager.GithubIntegration')
    def test_returns_none_when_no_issue_or_pr(
        self,
        mock_github_integration,
        mock_auth,
        mock_token_manager,
        mock_data_collector,
    ):
        """Test that None is returned when neither issue nor pull_request is in payload."""
        message = Message(
            source=SourceType.GITHUB,
            message={
                'installation': 12345,
                'payload': {
                    'repository': {'owner': {'login': 'owner'}, 'name': 'repo'},
                },
            },
        )

        manager = GithubManager(mock_token_manager, mock_data_collector)
        result = manager._get_issue_number_from_payload(message)

        assert result is None


class TestGetUserNotFoundMessageIntegration:
    """Integration tests to verify the user not found message content matches expectations."""

    def test_message_mentions_openhands_cloud(self):
        """Test that the message directs users to OpenHands Cloud."""
        message = get_user_not_found_message('testuser')
        assert 'OpenHands Cloud' in message

    def test_message_contains_actionable_instruction(self):
        """Test that the message tells users to sign up."""
        message = get_user_not_found_message('testuser')
        assert 'sign up' in message.lower()
        assert 'try again' in message.lower()

    def test_message_is_friendly_and_informative(self):
        """Test that the message is friendly and explains the situation."""
        message = get_user_not_found_message('testuser')
        assert 'it looks like' in message.lower()
        assert "haven't created an openhands account" in message.lower()


def test_init_laminar_for_external_falls_back_to_maybe_init_laminar(monkeypatch):
    """Test the local compatibility wrapper when the SDK helper is unavailable."""
    from integrations.github import github_manager

    mock_observability = type(sys)('openhands.sdk.observability')
    mock_observability.maybe_init_laminar = MagicMock()
    monkeypatch.setitem(sys.modules, 'openhands.sdk.observability', mock_observability)

    mock_laminar = MagicMock()
    mock_laminar.is_initialized.return_value = True
    mock_laminar.get_laminar_span_context.return_value = 'span-context'
    monkeypatch.setattr(github_manager, 'Laminar', mock_laminar)

    assert github_manager.init_laminar_for_external() == 'span-context'
    mock_observability.maybe_init_laminar.assert_called_once()


class TestLaminarObservability:
    """Test cases for Laminar observability integration."""

    @pytest.fixture(autouse=True)
    def mock_github_manager_dependencies(self, monkeypatch):
        """Patch GithubManager dependencies so Laminar behavior can be tested in isolation."""
        from integrations.github import github_manager

        mock_laminar = MagicMock()
        mock_laminar.is_initialized.return_value = False
        mock_laminar.get_laminar_span_context.return_value = None
        monkeypatch.setattr(github_manager, 'Laminar', mock_laminar)
        monkeypatch.setattr(github_manager, 'Auth', MagicMock())
        monkeypatch.setattr(github_manager, 'GithubIntegration', MagicMock())
        monkeypatch.setattr(
            github_manager,
            'get_saas_user_auth',
            AsyncMock(return_value=MagicMock()),
        )
        monkeypatch.setattr(github_manager, 'register_callback_processor', MagicMock())
        monkeypatch.setattr(github_manager, 'ENABLE_SOLVABILITY_ANALYSIS', False)

        mock_init_laminar_for_external = MagicMock(return_value=None)
        monkeypatch.setattr(
            github_manager,
            'init_laminar_for_external',
            mock_init_laminar_for_external,
        )

        mock_callback_module = type(sys)(
            'server.conversation_callback_processor.github_callback_processor'
        )
        mock_callback_module.GithubCallbackProcessor = MagicMock(
            return_value=MagicMock()
        )
        monkeypatch.setitem(
            sys.modules,
            'server.conversation_callback_processor.github_callback_processor',
            mock_callback_module,
        )

        return {
            'github_manager': github_manager,
            'laminar': mock_laminar,
            'init_laminar_for_external': mock_init_laminar_for_external,
        }

    @pytest.fixture
    def manager(self, mock_token_manager, mock_data_collector):
        """Create a GithubManager with outbound messaging mocked."""
        from integrations.github import github_manager

        manager = github_manager.GithubManager(mock_token_manager, mock_data_collector)
        manager.send_message = AsyncMock()
        return manager

    @pytest.fixture
    def mock_token_manager(self):
        """Create a mock token manager."""
        token_manager = MagicMock()
        token_manager.get_idp_token_from_idp_user_id = AsyncMock(
            return_value='test-token'
        )
        token_manager.load_org_token = AsyncMock(return_value='installation-token')
        return token_manager

    @pytest.fixture
    def mock_data_collector(self):
        """Create a mock data collector."""
        data_collector = MagicMock()
        data_collector.save_data = AsyncMock()
        return data_collector

    @pytest.fixture
    def mock_user_info(self):
        """Create a mock UserInfo object."""
        user_info = MagicMock()
        user_info.user_id = '123'
        user_info.username = 'testuser'
        user_info.keycloak_user_id = 'kc-123'
        return user_info

    @pytest.fixture
    def mock_github_view(self, mock_user_info):
        """Create a mock GithubViewType object."""
        from integrations.github.github_view import GithubIssue

        github_view = MagicMock(spec=GithubIssue)
        github_view.user_info = mock_user_info
        github_view.full_repo_name = 'test-owner/test-repo'
        github_view.issue_number = 42
        github_view.conversation_id = 'conv-123'
        github_view.installation_id = 12345
        github_view.v1_enabled = False

        github_view.initialize_new_conversation = AsyncMock(
            return_value=MagicMock(
                conversation_id='conv-123',
                selected_repository='test-owner/test-repo',
            )
        )
        github_view.create_new_conversation = AsyncMock()
        return github_view

    @pytest.mark.asyncio
    async def test_laminar_span_created_with_metadata_when_enabled(
        self,
        manager,
        mock_github_view,
        mock_github_manager_dependencies,
    ):
        """Test that Laminar span is created with correct metadata when Laminar is enabled."""
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_span_context = MagicMock()

        mock_github_manager_dependencies[
            'laminar'
        ].start_as_current_span.return_value = mock_span
        mock_github_manager_dependencies[
            'init_laminar_for_external'
        ].return_value = mock_span_context

        await manager.start_job(mock_github_view)

        mock_github_manager_dependencies[
            'laminar'
        ].start_as_current_span.assert_called_once_with(
            name='github-resolver',
            parent_span_context=mock_span_context,
        )
        mock_github_manager_dependencies[
            'laminar'
        ].set_trace_metadata.assert_called_once_with(
            {
                'source': 'github',
                'repo': 'test-owner/test-repo',
                'issue_number': '42',
                'username': 'testuser',
                'conversation_id': 'conv-123',
            }
        )
        mock_github_view.create_new_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_created_when_laminar_disabled(
        self,
        manager,
        mock_github_view,
        mock_github_manager_dependencies,
    ):
        """Test that conversation is created when Laminar is disabled."""
        mock_github_manager_dependencies[
            'init_laminar_for_external'
        ].return_value = None

        await manager.start_job(mock_github_view)

        mock_github_manager_dependencies[
            'laminar'
        ].start_as_current_span.assert_not_called()
        mock_github_view.create_new_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_created_when_laminar_span_setup_fails(
        self,
        manager,
        mock_github_view,
        mock_github_manager_dependencies,
    ):
        """Test that conversation is created even when Laminar span setup fails."""
        mock_github_manager_dependencies[
            'init_laminar_for_external'
        ].return_value = MagicMock()
        mock_github_manager_dependencies[
            'laminar'
        ].start_as_current_span.side_effect = RuntimeError('Laminar unavailable')

        await manager.start_job(mock_github_view)

        mock_github_view.create_new_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_laminar_flush_called_when_enabled(
        self,
        manager,
        mock_github_view,
        mock_github_manager_dependencies,
    ):
        """Test that Laminar.flush() is called when Laminar is enabled."""
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_github_manager_dependencies[
            'laminar'
        ].start_as_current_span.return_value = mock_span
        mock_github_manager_dependencies[
            'init_laminar_for_external'
        ].return_value = MagicMock()

        await manager.start_job(mock_github_view)

        mock_github_manager_dependencies['laminar'].flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_laminar_flush_not_called_when_disabled(
        self,
        manager,
        mock_github_view,
        mock_github_manager_dependencies,
    ):
        """Test that Laminar.flush() is NOT called when Laminar is disabled."""
        mock_github_manager_dependencies[
            'init_laminar_for_external'
        ].return_value = None

        await manager.start_job(mock_github_view)

        mock_github_manager_dependencies['laminar'].flush.assert_not_called()
