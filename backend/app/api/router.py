from fastapi import APIRouter, Depends

from app.api.routes import alarms, analysis, dashboard, devices, health, motors, settings, system
from app.core.security import get_current_user

protected = APIRouter(dependencies=[Depends(get_current_user)])
protected.include_router(dashboard.router)
protected.include_router(motors.router)
protected.include_router(analysis.router)
protected.include_router(alarms.router)
protected.include_router(devices.router)
protected.include_router(settings.router)
protected.include_router(system.router)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(protected)
