"""Bootstrap the first portal administrator from the trusted server console."""

import argparse

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db.session import SessionFactory
from app.domain.auth.service import (
    INVITATION_LIFETIME,
    invitation_url,
    invite_user,
    issue_token,
    origin_config,
)
from app.domain.models import PortalAuthToken, PortalPasskey, PortalUser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    args = parser.parse_args()
    settings = get_settings()
    origin_config(settings)
    with SessionFactory() as session:
        users = list(session.scalars(select(PortalUser).limit(2).with_for_update()))
        if not users:
            token = invite_user(session, args.email, admin=True, nmvo=True)
        else:
            user = users[0]
            if (
                len(users) != 1
                or user.email != args.email.strip().lower()
                or not user.is_admin
                or user.disabled_at
                or session.scalar(
                    select(PortalPasskey.id)
                    .where(PortalPasskey.user_id == user.id)
                    .limit(1)
                )
            ):
                parser.error(
                    "An administrator already exists. Invite users from the portal."
                )
            session.execute(
                delete(PortalAuthToken).where(PortalAuthToken.user_id == user.id)
            )
            token = issue_token(session, "invite", INVITATION_LIFETIME, user_id=user.id)
        session.commit()
    print(invitation_url(settings.portal_auth_origin, token))


if __name__ == "__main__":
    main()
