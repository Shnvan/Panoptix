from __future__ import annotations

from dataclasses import dataclass

import httpx

from cctv_api.core.config import Settings


class GitHubInviteConfigError(RuntimeError):
    pass


class GitHubInviteError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubInviteResult:
    invitation_id: int | None
    org: str
    status: str


def _configured_team_ids(settings: Settings) -> list[int]:
    raw = settings.GITHUB_INVITE_TEAM_IDS.strip()
    if not raw:
        return []
    team_ids: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            team_ids.append(int(item))
        except ValueError as exc:
            raise GitHubInviteConfigError("github-invite-team-ids-invalid") from exc
    return team_ids


def create_github_org_invitation(settings: Settings, *, email: str) -> GitHubInviteResult:
    org = settings.GITHUB_ORG.strip()
    token = settings.GITHUB_INVITE_TOKEN.strip()
    if not settings.GITHUB_INVITES_ENABLED or not org or not token or token == "replace-me":
        raise GitHubInviteConfigError("github-invites-not-configured")

    payload: dict[str, object] = {"email": email}
    team_ids = _configured_team_ids(settings)
    if team_ids:
        payload["team_ids"] = team_ids

    try:
        response = httpx.post(
            f"https://api.github.com/orgs/{org}/invitations",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=payload,
            timeout=settings.GITHUB_INVITE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise GitHubInviteError("github-invite-failed") from exc

    if response.status_code == 201:
        data = response.json()
        invitation_id = data.get("id")
        return GitHubInviteResult(
            invitation_id=invitation_id if isinstance(invitation_id, int) else None,
            org=org,
            status="invited",
        )

    if response.status_code == 422:
        message = ""
        try:
            body = response.json()
            raw_message = body.get("message")
            message = raw_message.lower() if isinstance(raw_message, str) else ""
        except ValueError:
            message = response.text.lower()
        if "already" in message or "pending" in message:
            return GitHubInviteResult(invitation_id=None, org=org, status="already_invited")

    raise GitHubInviteError("github-invite-failed")
