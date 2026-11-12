"""统一认证适配：直连模式或 SSO 网关代理模式。"""

from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.core.config import settings


@dataclass
class UserContext:
    name: str
    role: str
    auth_mode: str


def get_current_user(request: Request) -> UserContext:
    if settings.auth_mode == "proxy":
        name = request.headers.get(settings.auth_proxy_header, "").strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未通过统一身份认证，请从 SSO 入口访问",
            )
        role = request.headers.get(settings.auth_role_header, "观察员").strip() or "观察员"
        return UserContext(name=name, role=role, auth_mode="proxy")
    return UserContext(name=settings.default_user, role="设备科 · 观察员", auth_mode="off")
