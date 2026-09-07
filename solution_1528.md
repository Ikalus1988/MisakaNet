# Solution for #1528: feat: intake conversion receipt — notify source when its intake becomes a lesson

Here's a complete production-quality solution for this GitHub issue:

===FILE:.github/workflows/intake_receipt.yml===
name: Intake Receipt Notification

on:
  workflow_dispatch:
    inputs:
      intake_id:
        description: 'ID of the intake being promoted'
        required: true
      lesson_url:
        description: 'URL of the published lesson'
        required: true
      evidence_level:
        description: 'Evidence level of the lesson'
        required: true
      source_repo:
        description: 'Source repository to notify (owner/repo format)'
        required: true
      source_issue:
        description: 'Issue number in source repo to comment on'
        required: false

jobs:
  notify-source:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Create receipt comment
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const { intake_id, lesson_url, evidence_level, source_repo, source_issue } = context.payload.inputs;

            const [owner, repo] = source_repo.split('/');
            const commentBody = `🎉 Your submission (Intake #${intake_id}) has been promoted to a published lesson!\n\n` +
                               `📖 Lesson: ${lesson_url}\n` +
                               `📊 Evidence Level: ${evidence_level}\n\n` +
                               `This means your content was valuable enough to be included in our knowledge base. ` +
                               `Thanks for contributing!`;

            if (source_issue) {
              await github.rest.issues.createComment({
                owner,
                repo,
                issue_number: parseInt(source_issue),
                body: commentBody
              });
            } else {
              await github.rest.issues.create({
                owner,
                repo,
                title: `Your submission was promoted to a lesson`,
                body: commentBody
              });
            }
===END_FILE===

===FILE:src/intake_service.py===
import os
from typing import Optional
from dataclasses import dataclass
from github import Github

@dataclass
class IntakeMetadata:
    source_repo: str
    source_issue: Optional[int] = None
    evidence_level: Optional[str] = None

class IntakeService:
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github = Github(self.github_token) if self.github_token else None

    def promote_to_lesson(self, intake_id: str, lesson_url: str, metadata: IntakeMetadata):
        """Promote an intake to a lesson and notify the source"""
        if not self.github:
            raise ValueError("GitHub token not configured")

        # Trigger the GitHub Actions workflow
        workflow_id = "intake_receipt.yml"
        repo = self.github.get_repo(os.getenv('GITHUB_REPOSITORY'))

        workflow = repo.get_workflow(workflow_id)
        workflow.create_dispatch(
            ref="main",
            inputs={
                "intake_id": intake_id,
                "lesson_url": lesson_url,
                "evidence_level": metadata.evidence_level or "unknown",
                "source_repo": metadata.source_repo,
                "source_issue": str(metadata.source_issue) if metadata.source_issue else ""
            }
        )

        return {
            "status": "success",
            "message": f"Promotion initiated for intake {intake_id}"
        }
===END_FILE===

===FILE:tests/test_intake_service.py===
import os
import pytest
from unittest.mock import MagicMock, patch
from src.intake_service import IntakeService, IntakeMetadata

@pytest.fixture
def intake_service():
    os.environ['GITHUB_TOKEN'] = 'test_token'
    os.environ['GITHUB_REPOSITORY'] = 'test/repo'
    return IntakeService()

def test_promote_to_lesson_with_issue(intake_service):
    metadata = IntakeMetadata(
        source_repo="source/owner",
        source_issue=123,
        evidence_level="high"
    )

    with patch.object(intake_service.github, 'get_repo') as mock_get_repo:
        mock_repo = MagicMock()
        mock_workflow = MagicMock()
        mock_get_repo.return_value = mock_repo
        mock_repo.get_workflow.return_value = mock_workflow

        result = intake_service.promote_to_lesson("intake-123", "https://example.com/lesson", metadata)

        assert result["status"] == "success"
        mock_workflow.create_dispatch.assert_called_once_with(
            ref="main",
            inputs={
                "intake_id": "intake-123",
                "lesson_url": "https://example.com/lesson",
                "evidence_level": "high",
                "source_repo": "source/owner",
                "source_issue": "123"
            }
        )

def test_promote_to_lesson_without_issue(intake_service):
    metadata = IntakeMetadata(
        source_repo="source/owner",
        evidence_level="medium"
    )

    with patch.object(intake_service.github, 'get_repo') as mock_get_repo:
        mock_repo = MagicMock()
        mock_workflow = MagicMock()
        mock_get_repo.return_value = mock_repo
        mock_repo.get_workflow.return_value = mock_workflow

        result = intake_service.promote_to_lesson("intake-456", "https://example.com/lesson", metadata)

        assert result["status"] == "success"
        mock_workflow.create_dispatch.assert_called_once_with(
            ref="main",
            inputs={
                "intake_id": "intake-456",
                "lesson_url": "https://example.com/lesson",
                "evidence_level": "medium",
                "source_repo": "source/owner",
                "source_issue": ""
            }
        )
===END_FILE===

===FILE:README.md===
# Intake Conversion Receipt System

This system provides a feedback loop for content sources by notifying them when their intake submissions are promoted to published lessons.

## How It Works

1. When an intake is promoted to a lesson, the system:
   - Tracks the source repository and original issue/PR
   - Records the evidence level of the lesson
   - Triggers a GitHub Actions workflow to notify the source

2. The notification includes:
   - The original intake ID
   - Link to the published lesson
   - Evidence level of the lesson
   - A thank-you message acknowledging the contribution

## Implementation Details

### GitHub Actions Workflow
- `.github/workflows/intake_receipt.yml`: Handles the notification logic
- Can comment on existing issues or create new ones in the source repository

### Core Service
- `src/intake_service.py`: Python service that:
  - Tracks intake metadata
  - Triggers the notification workflow
  - Handles both issue comments and new issue creation

### Testing
- `tests/test_intake_service.py`: Unit tests for the core service

## Usage

1. Configure the GitHub token with appropriate permissions
2. Call `IntakeService.promote_to_lesson()` with:
   - Intake ID
   - Lesson URL
   - Metadata including source repo and optional issue number
3. The system will automatically notify the source
===END_FILE===

---
_Generated by DevilX BountyHub solver_
