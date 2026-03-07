# Verification plan (Fixpack-8 / MUST-6)

## Objective
Validate truthful separation between generic room-name handling and real-home evidence status.

## Commands
1) Map room logic in code
```bash
rg -n "def derive_room_id_scoped|payload.room|payload.area|display_name|sensor_room_map|fallback" backend/util/room_id.py backend/main.py backend/routes/rooms.py
```

2) Scan for explicit variant hardcoding in repo
```bash
rg -n "\bbod\b|\bloft\b|kjellerstue" backend
```

3) Verify MUST-6 wording in docs
```bash
rg -n "MUST-6: romnavn-varianter|CHECK-ROOM-01|CHECK-ROOM-02" docs/v2/ROOM_MAPPING.md
```

4) Verify claim registration in SoT checklist
```bash
rg -n "SOT-041|Room-name variant support" docs/audit/sot-claims-v1.md
```

5) Verify Control Tower append exists
```bash
tail -n 40 docs/audit/AgingOS_CONTROL_TOWER.md
```
