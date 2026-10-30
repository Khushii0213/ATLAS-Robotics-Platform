from __future__ import annotations

import asyncio
import csv
import io
import math
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


UTC = timezone.utc

def now() -> datetime:
    return datetime.now(UTC)


class Status(str, Enum):
    OPERATIONAL = "operational"; IDLE = "idle"; EXECUTING = "executing"; OFFLINE = "offline"; FAULT = "fault"; ESTOP = "emergency_stopped"

class MissionStatus(str, Enum):
    DRAFT = "draft"; QUEUED = "queued"; ASSIGNED = "assigned"; EXECUTING = "executing"; PAUSED = "paused"; COMPLETED = "completed"; FAILED = "failed"; CANCELLED = "cancelled"

class Robot(BaseModel):
    id: str; name: str; model: str = "ATLAS AMR-2"; serial_number: str; firmware: str = "2.8.4"
    status: Status; battery: float; x: float; y: float; orientation: float; velocity: float = 0
    temperature: float = 34; latency: int = 18; packet_loss: float = 0; current_mission: str | None = None
    heartbeat: datetime = Field(default_factory=now); uptime_hours: float = 314.2; errors: int = 0; fault: str | None = None

class Mission(BaseModel):
    id: str; name: str; robot_id: str | None; customer: str; start: str; destination: str; priority: str
    status: MissionStatus; created_at: datetime = Field(default_factory=now); started_at: datetime | None = None
    completed_at: datetime | None = None; distance: float = 0; progress: int = 0; events: list[dict[str, Any]] = Field(default_factory=list)

class Alert(BaseModel):
    id: str; robot_id: str; severity: str; code: str; description: str; probable_cause: str
    recommendation: str; status: str = "open"; detected_at: datetime = Field(default_factory=now)

class Log(BaseModel):
    timestamp: datetime = Field(default_factory=now); severity: str; source: str; robot_id: str | None = None
    component: str; event_code: str; message: str

class CommandRequest(BaseModel):
    command: str = Field(pattern="^(forward|backward|left|right|stop|estop|clear_estop)$")
    speed: float = Field(default=0.35, ge=0, le=1)

class MissionRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80); robot_id: str | None = None; customer: str = "Northstar Logistics"
    start: str = "Inbound Dock"; destination: str; priority: str = Field(default="normal", pattern="^(low|normal|high|critical)$")

class FaultRequest(BaseModel):
    robot_id: str; fault: str = Field(pattern="^(low_battery|network_degradation|high_temperature|sensor_timeout|localization_drift|navigation_failure|obstacle_blockage|communication_loss|motor_controller_error)$")

class Store:
    def __init__(self): self.reset()
    def reset(self):
        base = now() - timedelta(minutes=20)
        self.robots: dict[str, Robot] = {
            "ATLAS-01": Robot(id="ATLAS-01", name="Pioneer", serial_number="AMR-24-001", status=Status.OPERATIONAL, battery=88, x=14, y=16, orientation=15),
            "ATLAS-02": Robot(id="ATLAS-02", name="Vector", serial_number="AMR-24-002", status=Status.IDLE, battery=76, x=40, y=13, orientation=90),
            "ATLAS-03": Robot(id="ATLAS-03", name="Relay", serial_number="AMR-24-003", status=Status.EXECUTING, battery=63, x=59, y=34, orientation=180, current_mission="MIS-1003", velocity=.45),
            "ATLAS-04": Robot(id="ATLAS-04", name="Harbor", serial_number="AMR-24-004", status=Status.FAULT, battery=14, x=20, y=44, orientation=270, fault="low_battery", errors=1),
            "ATLAS-05": Robot(id="ATLAS-05", name="Orbit", serial_number="AMR-24-005", status=Status.OPERATIONAL, battery=72, x=77, y=50, orientation=330, latency=218, packet_loss=8.4, fault="network_degradation", errors=1),
        }
        self.missions: dict[str, Mission] = {
            "MIS-1001": Mission(id="MIS-1001", name="Pallet transfer A-17", robot_id="ATLAS-01", customer="Northstar Logistics", start="Inbound Dock", destination="Storage A17", priority="normal", status=MissionStatus.COMPLETED, progress=100, distance=142, created_at=base, completed_at=base+timedelta(minutes=9), events=[{"at":base.isoformat(),"message":"Mission created"},{"at":(base+timedelta(minutes=9)).isoformat(),"message":"Delivered to Storage A17"}]),
            "MIS-1002": Mission(id="MIS-1002", name="Line-side replenishment", robot_id="ATLAS-02", customer="Apex Manufacturing", start="Kitting", destination="Line 4", priority="high", status=MissionStatus.QUEUED, distance=86),
            "MIS-1003": Mission(id="MIS-1003", name="Outbound staging run", robot_id="ATLAS-03", customer="Northstar Logistics", start="Storage B", destination="Outbound Dock", priority="high", status=MissionStatus.EXECUTING, progress=47, distance=183),
            "MIS-1004": Mission(id="MIS-1004", name="Charge cycle", robot_id="ATLAS-04", customer="Northstar Logistics", start="Zone C", destination="Charge 1", priority="critical", status=MissionStatus.PAUSED, distance=35),
            "MIS-1005": Mission(id="MIS-1005", name="Returns collection", robot_id="ATLAS-05", customer="Northstar Logistics", start="Returns", destination="QA Bay", priority="normal", status=MissionStatus.FAILED, progress=23, distance=67),
        }
        self.alerts = [Alert(id="ALT-001", robot_id="ATLAS-04", severity="warning", code="BAT-LOW", description="Battery below operational threshold", probable_cause="Extended operation without charge", recommendation="Route to Charge 1 before dispatch."), Alert(id="ALT-002", robot_id="ATLAS-05", severity="warning", code="NET-HIGH-LAT", description="Network latency exceeds 200 ms", probable_cause="Suggested: coverage gap near outbound zone", recommendation="Inspect access point coverage and roaming logs.")]
        self.logs: list[Log] = []
        self.audit: list[dict[str, Any]] = []
        self.sequence = 1005
        for r in self.robots.values():
            for i in range(12): self.logs.append(Log(timestamp=base+timedelta(minutes=i), severity="INFO", source="simulator", robot_id=r.id, component="telemetry", event_code="TEL-HEARTBEAT", message=f"Heartbeat received; battery={r.battery-i*.2:.1f}%"))
        self._audit("simulation", "reset", "Simulation returned to deterministic baseline")
    def _log(self, severity, source, robot, component, code, message): self.logs.append(Log(severity=severity,source=source,robot_id=robot,component=component,event_code=code,message=message))
    def _audit(self, actor, action, detail): self.audit.append({"timestamp":now().isoformat(), "actor":actor, "action":action, "detail":detail})

store = Store()

FAULTS = {
    "low_battery": ("BAT-LOW", "warning", "Battery below operational threshold", "Extended operation without charge", "Route robot to a charging station."),
    "network_degradation": ("NET-HIGH-LAT", "warning", "Network latency exceeds operational budget", "Suggested: RF coverage or roaming issue", "Inspect access point coverage and switch telemetry."),
    "high_temperature": ("MOTOR-HOT", "critical", "Motor controller temperature above safe range", "Suggested: sustained load or cooling issue", "Stop the robot and inspect cooling and motor load."),
    "sensor_timeout": ("SENS-TIMEOUT", "critical", "Lidar telemetry timeout", "Suggested: sensor connection fault", "Inspect sensor power and data link."),
    "localization_drift": ("LOC-DRIFT", "warning", "Localization confidence degraded", "Suggested: map mismatch or wheel slip", "Re-localize and verify map landmarks."),
    "navigation_failure": ("NAV-FAIL", "critical", "Planner failed to generate route", "Suggested: blocked route or map issue", "Inspect route blockage and navigation stack."),
    "obstacle_blockage": ("NAV-BLOCK", "warning", "Obstacle persists on planned path", "Suggested: staging obstruction", "Clear path or revise route."),
    "communication_loss": ("NET-LOST", "critical", "Robot communication lost", "Suggested: AP loss or power interruption", "Verify power and network reachability."),
    "motor_controller_error": ("MOTOR-CTRL", "critical", "Motor controller reports a fault", "Suggested: drive electronics issue", "Keep stopped and inspect controller diagnostics."),
}

def robot_or_404(robot_id: str) -> Robot:
    if robot_id not in store.robots: raise HTTPException(404, "Robot not found")
    return store.robots[robot_id]

def mission_or_404(mid: str) -> Mission:
    if mid not in store.missions: raise HTTPException(404, "Mission not found")
    return store.missions[mid]

def health_score(r: Robot):
    penalties = (max(0, 30-r.battery)*1.3) + (max(0,r.temperature-45)*1.5) + (20 if r.latency>150 else 0) + (30 if r.fault else 0) + (30 if r.status in [Status.OFFLINE,Status.ESTOP] else 0)
    return max(0, round(100-penalties))

def preflight(m: Mission):
    issues=[]
    if not m.robot_id: issues.append("No robot assigned")
    else:
        r=robot_or_404(m.robot_id)
        if r.status == Status.OFFLINE: issues.append("Robot is offline")
        if r.status == Status.ESTOP: issues.append("Emergency stop is engaged")
        if r.battery < 25: issues.append("Battery below 25%")
        if r.fault in ["navigation_failure","sensor_timeout","motor_controller_error","communication_loss"]: issues.append(f"Blocking fault: {r.fault}")
    if not m.destination.strip(): issues.append("Destination is required")
    return {"ready": not issues, "checks": [{"name":"Robot online", "state":"pass" if not any('offline' in x for x in issues) else "fail"},{"name":"Battery sufficient", "state":"pass" if not any('Battery' in x for x in issues) else "fail"},{"name":"Safety state", "state":"pass" if not any('Emergency' in x or 'Blocking' in x for x in issues) else "fail"}], "reasons":issues}

async def simulation_loop():
    rng=random.Random(42)
    while True:
        await asyncio.sleep(1)
        for r in store.robots.values():
            if r.status not in [Status.OFFLINE,Status.ESTOP]:
                r.heartbeat=now(); r.temperature=max(27, min(78, r.temperature+rng.uniform(-.2,.3)))
                if r.status==Status.EXECUTING:
                    r.battery=max(0,r.battery-.035); r.x=max(3,min(97,r.x+math.cos(math.radians(r.orientation))*r.velocity)); r.y=max(3,min(57,r.y+math.sin(math.radians(r.orientation))*r.velocity))
                    if r.current_mission:
                        m=store.missions.get(r.current_mission)
                        if m and m.status==MissionStatus.EXECUTING:
                            m.progress=min(100,m.progress+1)
                            if m.progress>=100:
                                m.status=MissionStatus.COMPLETED;m.completed_at=now();r.status=Status.IDLE;r.velocity=0;r.current_mission=None;store._log("INFO","mission",r.id,"mission","MIS-COMPLETE",f"{m.name} completed")
                if r.fault=="low_battery": r.battery=max(4,r.battery-.01)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task=asyncio.create_task(simulation_loop()); yield; task.cancel()

app=FastAPI(title="ATLAS Robotics API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS","http://localhost:5173").split(","), allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health(): return {"status":"healthy","mode":"simulation","version":"1.0.0","timestamp":now()}

@app.get("/api/robots")
def robots(status: Status|None=None, q: str=""):
    data=list(store.robots.values());
    if status: data=[r for r in data if r.status==status]
    if q: data=[r for r in data if q.lower() in (r.id+r.name+r.model).lower()]
    return {"items":[{**r.model_dump(),"health_score":health_score(r)} for r in data],"total":len(data)}

@app.get("/api/robots/{robot_id}")
def robot(robot_id:str):
    r=robot_or_404(robot_id); return {**r.model_dump(),"health_score":health_score(r),"health_factors":{"battery":r.battery,"temperature":r.temperature,"latency":r.latency,"active_fault":r.fault}}

@app.get("/api/robots/{robot_id}/telemetry")
def telemetry(robot_id:str):
    r=robot_or_404(robot_id); points=[]
    for i in range(24): points.append({"timestamp":(now()-timedelta(minutes=24-i)).isoformat(),"battery":max(0,r.battery+(24-i)*.35),"latency":max(2,r.latency+(i%5-2)*4),"temperature":r.temperature+(i%6-3)*.4})
    return {"robot_id":robot_id,"items":points}

@app.post("/api/robots/{robot_id}/commands")
def command(robot_id:str, body:CommandRequest):
    r=robot_or_404(robot_id)
    if body.command=="estop": r.status=Status.ESTOP;r.velocity=0;store._audit("operator","emergency_stop",robot_id);store._log("CRITICAL","teleop",robot_id,"safety","ESTOP","Emergency stop engaged")
    elif body.command=="clear_estop":
        if r.status!=Status.ESTOP: raise HTTPException(409,"Emergency stop is not engaged")
        r.status=Status.IDLE;store._audit("operator","clear_estop",robot_id)
    elif body.command=="stop": r.velocity=0; r.status=Status.IDLE if r.status==Status.EXECUTING and not r.current_mission else r.status;store._audit("operator","stop",robot_id)
    else:
        if r.status in [Status.OFFLINE,Status.ESTOP]: raise HTTPException(409,f"Command rejected: robot is {r.status.value}")
        if r.fault in ["motor_controller_error","communication_loss"]: raise HTTPException(409,"Command rejected: blocking fault")
        vectors={"forward":(0,1),"backward":(0,-1),"left":(-1,0),"right":(1,0)}; dx,dy=vectors[body.command]; r.x=max(2,min(98,r.x+dx*body.speed*5));r.y=max(2,min(58,r.y+dy*body.speed*5));r.velocity=body.speed;r.status=Status.OPERATIONAL;store._audit("operator",f"teleop_{body.command}",f"{robot_id} at {body.speed}")
    store._log("INFO","teleop",robot_id,"command","CMD-ACK",f"Command {body.command} acknowledged")
    return {"accepted":True,"robot":r,"acknowledgment":f"{body.command} acknowledged"}

@app.post("/api/robots/{robot_id}/stop")
def stop(robot_id:str): return command(robot_id,CommandRequest(command="stop"))

@app.get("/api/missions")
def missions(status:MissionStatus|None=None):
    data=list(store.missions.values()); return {"items":[m.model_dump() for m in data if not status or m.status==status],"total":len(data)}

@app.post("/api/missions")
def create_mission(body:MissionRequest):
    store.sequence+=1; mid=f"MIS-{store.sequence}";m=Mission(id=mid,**body.model_dump(),status=MissionStatus.ASSIGNED if body.robot_id else MissionStatus.DRAFT);m.events.append({"at":now().isoformat(),"message":"Mission created"});store.missions[mid]=m;store._audit("operator","mission_created",mid);return m

@app.get("/api/missions/{mission_id}")
def get_mission(mission_id:str): return mission_or_404(mission_id)

@app.get("/api/missions/{mission_id}/preflight")
def mission_preflight(mission_id:str): return preflight(mission_or_404(mission_id))

@app.post("/api/missions/{mission_id}/start")
def start_mission(mission_id:str):
    m=mission_or_404(mission_id);check=preflight(m)
    if not check["ready"]: raise HTTPException(409,{"message":"Preflight failed","reasons":check["reasons"]})
    r=robot_or_404(m.robot_id);m.status=MissionStatus.EXECUTING;m.started_at=now();m.events.append({"at":now().isoformat(),"message":"Mission started"});r.status=Status.EXECUTING;r.current_mission=m.id;r.velocity=.45;store._audit("operator","mission_started",m.id);return m

@app.post("/api/missions/{mission_id}/{action}")
def mission_action(mission_id:str,action:str):
    if action not in ["pause","resume","cancel"]: raise HTTPException(404,"Unknown mission action")
    m=mission_or_404(mission_id)
    states={"pause":MissionStatus.PAUSED,"resume":MissionStatus.EXECUTING,"cancel":MissionStatus.CANCELLED};m.status=states[action];m.events.append({"at":now().isoformat(),"message":f"Mission {action}d"})
    if m.robot_id:
        r=robot_or_404(m.robot_id)
        if action=="resume":r.status=Status.EXECUTING;r.current_mission=m.id;r.velocity=.45
        else:r.status=Status.IDLE;r.velocity=0;r.current_mission=None
    store._audit("operator",f"mission_{action}",m.id);return m

@app.get("/api/alerts")
def alerts(status:str|None=None): return {"items":[a for a in store.alerts if not status or a.status==status]}

@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id:str):
    a=next((x for x in store.alerts if x.id==alert_id),None)
    if not a: raise HTTPException(404,"Alert not found")
    a.status="resolved";r=robot_or_404(a.robot_id);r.fault=None;r.errors=max(0,r.errors-1)
    if r.status==Status.FAULT:r.status=Status.IDLE
    store._audit("operator","alert_resolved",alert_id);return a

@app.post("/api/simulation/faults")
def inject_fault(body:FaultRequest):
    r=robot_or_404(body.robot_id);code,severity,desc,cause,recommend=FAULTS[body.fault];r.fault=body.fault;r.errors+=1
    if body.fault=="communication_loss":r.status=Status.OFFLINE
    elif body.fault in ["motor_controller_error","sensor_timeout","navigation_failure","high_temperature"]:r.status=Status.FAULT
    if body.fault=="low_battery":r.battery=min(r.battery,14)
    if body.fault=="network_degradation":r.latency=240;r.packet_loss=9
    if body.fault=="high_temperature":r.temperature=76
    a=Alert(id=f"ALT-{len(store.alerts)+1:03d}",robot_id=r.id,severity=severity,code=code,description=desc,probable_cause=cause,recommendation=recommend);store.alerts.append(a);store._audit("operator","fault_injected",f"{body.fault}:{r.id}");store._log(severity.upper(),"diagnostics",r.id,"health",code,desc);return {"alert":a,"robot":r}

@app.post("/api/simulation/reset")
def reset(): store.reset();return {"ok":True,"message":"Deterministic baseline restored"}

@app.get("/api/logs")
def logs(q:str="", severity:str|None=None, robot_id:str|None=None):
    data=store.logs
    if q:data=[x for x in data if q.lower() in x.message.lower()]
    if severity:data=[x for x in data if x.severity.lower()==severity.lower()]
    if robot_id:data=[x for x in data if x.robot_id==robot_id]
    return {"items":[x.model_dump() for x in data[-200:]]}

@app.get("/api/logs/export")
def export_logs():
    out=io.StringIO();w=csv.writer(out);w.writerow(["timestamp","severity","source","robot_id","component","event_code","message"])
    for l in store.logs:w.writerow([l.timestamp,l.severity,l.source,l.robot_id,l.component,l.event_code,l.message])
    return StreamingResponse(iter([out.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=atlas-logs.csv"})

@app.get("/api/analytics")
def analytics():
    ms=list(store.missions.values());rs=list(store.robots.values()); return {"utilization":[{"hour":f"{h:02d}:00","value":48+(h%5)*7} for h in range(8,18)],"battery":[{"robot":r.id,"battery":r.battery} for r in rs],"mission_completion_rate":round(100*len([m for m in ms if m.status==MissionStatus.COMPLETED])/len(ms)),"average_duration_minutes":18,"fleet_uptime":99.2,"fault_frequency":[{"name":a.code,"value":1} for a in store.alerts if a.status=="open"]}

@app.get("/api/deployments")
def deployments(): return {"items":[{"id":"DEP-001","customer":"Northstar Logistics","facility":"Noida Distribution Center","location":"Noida, IN","robots":5,"status":"Operational","software_version":"2.8.4","date":"2026-09-16","last_health_check":"2026-10-30T08:00:00Z","engineer":"A. Mehta"},{"id":"DEP-002","customer":"Apex Manufacturing","facility":"Pune Plant 4","location":"Pune, IN","robots":3,"status":"Commissioning","software_version":"2.8.4","date":"2026-10-12","last_health_check":"2026-10-30T07:30:00Z","engineer":"J. Shah"}]}

@app.get("/api/deployments/{deployment_id}/readiness")
def readiness(deployment_id:str): return {"deployment_id":deployment_id,"state":"warning","checks":[{"name":"Network connectivity","state":"pass"},{"name":"Robot connectivity","state":"pass"},{"name":"Battery and charging","state":"warning"},{"name":"Localization","state":"pass"},{"name":"Mapping","state":"pass"},{"name":"Navigation","state":"pass"},{"name":"Safety checks","state":"pass"},{"name":"Mission execution","state":"warning"},{"name":"API connectivity","state":"pass"}]}

@app.get("/api/customers")
def customers(): return {"items":[{"id":"CUS-001","name":"Northstar Logistics","facilities":1,"open_issues":2},{"id":"CUS-002","name":"Apex Manufacturing","facilities":1,"open_issues":1}]}

@app.get("/api/support")
def support(): return {"items":[{"id":"SUP-107","customer":"Northstar Logistics","title":"Outbound Wi-Fi handoff investigation","priority":"high","status":"In progress","engineer":"A. Mehta","notes":"Customer updated; RF survey scheduled."},{"id":"SUP-108","customer":"Apex Manufacturing","title":"Line 4 waypoint tuning","priority":"normal","status":"Open","engineer":"J. Shah","notes":"Awaiting latest facility layout."}]}

@app.get("/api/audit")
def audit(): return {"items":store.audit[-200:]}

@app.websocket("/ws/fleet")
async def fleet_ws(ws:WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json({"type":"fleet_update","timestamp":now().isoformat(),"robots":[r.model_dump(mode="json") for r in store.robots.values()]});await asyncio.sleep(1)
    except WebSocketDisconnect: pass
