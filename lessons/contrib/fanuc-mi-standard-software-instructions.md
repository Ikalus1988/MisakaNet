---
title: "FANUC MI Standard Software — Complete Instruction Reference (MI01-MI22)"
domain: "fanuc"
subdomain: "tp-programming"
tags: ["mi-standard", "mi01-cmn", "mi02-tch", "mi04-ssw", "mi08-dsp", "mi11-apl", "mi14-spr", "mi22-fds", "automotive", "welding", "gluing", "riveting"]
status: "published"
source: "internal-training"
confidence: "0.9"
created: "2026-07-14"
---

## Problem

MI Standard Software is a comprehensive instruction library for automotive FANUC robots, covering PLC communication, tool change, spot welding, gluing, SPR riveting, FDS, stud welding, and more. Engineers need a quick reference for all MI module instructions and their parameters.

## Solution

### Architecture Overview

MI Standard Software uses KAREL + TP hybrid architecture. Instructions are called via `CALL MIxx_MOD(parameters)`.

### MI01_CMN — PLC Communication

Base module for robot-PLC interaction. Background program starts automatically with robot.

**Instructions:**

| Instruction | Function | Format |
|-------------|----------|--------|
| Init | Reset collision zones, fixtures, group outputs; check home/pounce; verify MI02 installation | `CALL MI01_CMN(Init, '...')` |
| CollZone | Collision zone request/release | `CALL MI01_CMN(CollZone, Request/Release, ZoneNo.=1, '...')` |
| Segment | Send segment number to PLC | `CALL MI01_CMN(Segment, SegNo.=1, '...')` |
| DecisionCode | Set register or output to PLC | `CALL MI01_CMN(DecisionCode, SetToReg/OutToPLC, '...')` |
| Fixture | Fixture IN/OUT control | `CALL MI01_CMN(Fixture, IN/OUT, FixNo.=1, '...')` |
| PressCheck | Pressure detection | `CALL MI01_CMN(PressCheck, '...')` |
| FestoCheck | RIP detection (Festo) | `CALL MI01_CMN(FestoCheck, '...')` |

**CollZone parameters:**
- Param 1: `CollZone`
- Param 2: `Request` or `Release`
- Param 3: `ZoneNo.` (1-32)
- Param 4: Comment (max 32 chars)

### MI02_TCH — Tool Change

| Instruction | Function | Format |
|-------------|----------|--------|
| GunChange | Switch tool | `CALL MI02_TCH(GunChange, GunNo.=1, '...')` |
| GunOpen | Open tool | `CALL MI02_TCH(GunOpen, '...')` |
| GunClose | Close tool | `CALL MI02_TCH(GunClose, '...')` |

### MI03_GRP — Material Handling

```fanuc
CALL MI03_GRP(Init, '...')
CALL MI03_GRP(Step1, '...')
```

### MI04_SSW — Servo Spot Welding

| Instruction | Function | Format |
|-------------|----------|--------|
| Weld | Spot weld | `CALL MI04_SSW(Weld, SpotNum=1, StyleNum=1, '...')` |
| TipDress | Tip dress | `CALL MI04_SSW(TipDress, TipDressNum=1, '...')` |
| TIPCHG | Tip change (new) | `CALL MI04_SSW(TIPCHG, TipCHGNum=1, '...')` |
| FRES-TD | Tip dress (new) | `CALL MI04_SSW(FRES-TD, FRESNum=1, '...')` |

**Tip dress compensation:**
- System multiplies GI[121] value by `Tip dress scale` coefficient
- Compensation applied to Tool 1 TCP
- `Update`: Apply GI[121] × scale to Tool 1
- `New Tip`: Restore original TCP from saved value

**Config:** MENU → TEST CYCLE → MI GUI → MI04 Setup

### MI08_DSP — Gluing

| Instruction | Function | Format |
|-------------|----------|--------|
| Glue_Init | Initialize | `CALL MI08_DSP(Glue_Init, '...')` |
| Glue_Start | Start gluing | `CALL MI08_DSP(Glue_Start, NozzleNum=1, TypeID=1, '...')` |
| Glue_Purge | Purge gun | `CALL MI08_DSP(Glue_Purge, NozzleNum=1, '...')` |
| Glue_Fill | Fill | `CALL MI08_DSP(Glue_Fill, NozzleNum=1, '...')` |
| Glue_End | End | `CALL MI08_DSP(Glue_End, '...')` |

**Config:** MENU → TEST CYCLE → MI GUI → MI08 Setup

### MI09_DSD — Glue Detection

**BetterWay brand:**
- `Check`: Detection
- `Start`: Start nozzle
- `Reset`: Reset
- `SendBSNNNum`: Send body serial number
- `Job Start`: Process start

**Coherix 2D/3D brand:**
- `Check`, `Camera On/Off`, `Reset`, `SendBSNNNum`, `Job Start`, `Control Run Mode`, `Control Gun`

### MI11_APL — Arplas/Dimple Welding

**Arplas instructions:**

| Instruction | Function | Format |
|-------------|----------|--------|
| ArplasWeld | Weld | `CALL MI11_APL(Arplas, ArplasWeld, SpotNum=1, StrokePos=1000, '...')` |
| Tipdress Update | Update TCP after dress | `CALL MI11_APL(Arplas, Tipdress, Update, '...')` |
| Tipdress New Tip | Restore TCP | `CALL MI11_APL(Arplas, Tipdress, New Tip, '...')` |

**Dimple instructions:**
- `DimplePosCheck`: Pre-process check
- `CloseGun`: Close gun process (delay then open, check pressure sensor)

### MI13_RVH — SPR Riveting (Old Tucker)

| Instruction | Function | Format |
|-------------|----------|--------|
| Init | Initialize | `CALL MI13_RVH(Init, GunNo.=1, GunOpen[mm]=100, '...')` |
| Rivet | Rivet | `CALL MI13_RVH(Rivet, RivetNo.=1, NextRivetNo.=1, GunNo.=1, GunOpen[mm]=100, '...')` |
| Positioning | Open rivet gun | `CALL MI13_RVH(Positioning, GunNo.=1, GunOpen[mm]=100, GunOpenCtrl, '...')` |
| PrepareDock | Magazine pre/post | `CALL MI13_RVH(PrepareDock, GunNo.=1, ActivateON/OFF, '...')` |
| LoadEPF | Load rivets | `CALL MI13_RVH(LoadEPF, GunNo.=1, '...')` |
| GunState | Gun connect control | `CALL MI13_RVH(GunState, GunNo.=1, Couple/Decouple, '...')` |

### MI14_SPR — SPR Riveting (New Tucker)

| Instruction | Function | Format |
|-------------|----------|--------|
| Init | Initialize | `CALL MI14_SPR(Init, GunNo.=1, GunOpen[mm]=100, '...')` |
| Rivet | Rivet | `CALL MI14_SPR(Rivet, GunNo.=1, RivetNo.=1, NextRivetNo.=1, GunOpen[mm]=100, '...')` |
| Reload | Load rivets | `CALL MI14_SPR(Reload, GunNo.=1, RivetNo.=1, '...')` |
| Docking | Gun connect | `CALL MI14_SPR(Docking, GunNo.=1, Connect/Disconnect, '...')` |
| Magazine | Magazine control | `CALL MI14_SPR(Magazine, GunNo.=1, Preparation/ReadyToFill/PostProcessing, '...')` |
| SendBSNNNum | Send body code | `CALL MI14_SPR(SendBSNNNum, GunNo.=1, '...')` |

### MI15_SPR — SPR Riveting (Guji)

Instructions: Init, Rivet, Positioning, GunState, Prepare, FillMag, Reload, SendBSNNNum, DieCheck

### MI17_OBJ — Vision Detection

```fanuc
CALL MI17_OBJ(SendBSNNNum, '...')
```
DO[172] sends 5s pulse.

### MI19_CLI — Press Riveting

| Instruction | Function | Format |
|-------------|----------|--------|
| INIT | Initialize | `CALL MI19_CLI(INIT, '...')` |
| LOAD | Pre-feed rivet | `CALL MI19_CLI(LOAD, Check/NoCheck, '...')` |
| TOX_Start | Start press program | `CALL MI19_CLI(TOX_Start, ProgNum=1, '...')` |
| TOX_End | Close press program | `CALL MI19_CLI(TOX_End, '...')` |

Mode: `servo` (default) or `hydraulic`

### MI20_SWH — Stud Welding (Old Tucker)

| Instruction | Function | Format |
|-------------|----------|--------|
| Init | Initialize | `CALL MI20_SWH(Init, '...')` |
| Start | Stud weld | `CALL MI20_SWH(Start, HeadNo=1, StudID='1', '...')` |
| SendBSNNNum | Send body code | `CALL MI20_SWH(SendBSNNNum, '...')` |

StudID: string format, range 1-134217728, default 1.
Gun Type: Single or Double.

### MI21_SWH — Stud Welding (New Tucker)

Similar to MI20, but StudID range 1-999999999. Additional timeout parameters:
- System Ready Timeout
- Process Complete Timeout
- Fault Timeout
- Head Back Timeout
- Weld Inside Tol Timeout

### MI22_FDS — Flow Drill Screwing

| Instruction | Function | Format |
|-------------|----------|--------|
| Init | Initialize | `CALL MI22_FDS(Init, GunNo.=1, '...')` |
| Drill | FDS process | `CALL MI22_FDS(Drill, PointNo.=1, TypeID=1, GunNo.=1, '...')` |
| PrepareScrew | Prepare screw | `CALL MI22_FDS(PrepareScrew, GunNo.=1, PointNo.=1, TypeID=1, '...')` |
| Adjust | Adjust | `CALL MI22_FDS(Adjust, GunNo.=1, '...')` |
| GunState | Tool connect/disconnect | `CALL MI22_FDS(GunState, Couple/Decouple, GunNo.=1, '...')` |
| EjectScrew | Eject screw | `CALL MI22_FDS(EjectScrew, GunNo.=1, '...')` |
| FeedScrew | Feed screw | `CALL MI22_FDS(FeedScrew, GunNo.=1, '...')` |

### Diagnostic Alarm Display

When WAIT DI/GI conditions are not met, the system jumps to user screen showing:
```
MI01|collision zone return collision zone[1] is occupied
WAITING FOR: DI[89] = ON; (Zone Ready 1)
```

## Verification

1. Call MI01_CMN Init in a test program — verify signals reset correctly
2. Call MI01_CMN CollZone Request/Release — verify DI signals toggle
3. Call MI04_SSW Weld — verify spot weld sequence executes
4. Call MI08_DSP Glue_Start/End — verify glue sequence executes
5. Check MI GUI config screens exist for each module

## Notes

- MI standard software requires specific options installed on the controller
- MI01_CMN background program starts automatically with robot power-on
- Collision zone numbers (1-32) are shared across all robots in the system
- Tip dress compensation uses GI[121] × scale factor — verify GI[121] is updated by weld controller
- All MI instructions support trailing comment strings for debugging
