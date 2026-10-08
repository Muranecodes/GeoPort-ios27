# 05: 自動導航地圖模式、OSRM 步行路網規劃與視角鎖定

**What to build:** An intuitive end-to-end navigation user experience on the Leaflet map: an "Auto Navigation" toolbar mode switch, click-to-navigate destination routing via the OSRM pedestrian footway network, fallback to direct interpolation, camera tracking with lock/unlock toggle, and arrival toast alerts.

**Blocked by:** 04: 後端 1Hz 背景巡航引擎、到達停止與狀態 HUD

**Status:** completed

- [x] Add an "Auto Navigation" mode button to the Leaflet toolbar; clicking it toggles auto-nav mode on/off with visual indicator.
- [x] In Auto-Nav mode, clicking any point on the map queries OSRM foot routing (`https://routing.openstreetmap.de/routed-foot/route/v1/`) from current position to clicked destination.
- [x] If OSRM returns valid geometry, draw the route polyline on the map and trigger `POST /start_navigation` with the route points.
- [x] If OSRM is unreachable or fails, cleanly fall back to a direct 2-point line from current location to destination and proceed with navigation.
- [x] Implement camera auto-center behavior that smoothly pans the map to keep the moving marker in view during navigation.
- [x] Add a camera lock/unlock toggle button on the map allowing the user to unbind auto-panning and inspect the map freely.
- [x] Display an arrival toast alert ("已到達目的地") when navigation reports completion and clean up route polylines.
- [x] Perform full end-to-end testing across all user stories.
