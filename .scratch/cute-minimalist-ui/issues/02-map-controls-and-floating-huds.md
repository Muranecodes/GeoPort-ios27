# 02: 地圖底圖升級、左上角雙膠囊工具列精簡與「🌸 種花」櫻花粉懸浮面板

**What to build:** Upgrade the central map canvas to default to the pastel `CartoDB Voyager` base map and render **Auto Navigation** routes in a soft sage-green stroke; declutter the top-left map toolbar so only **Auto Navigation** (`🧭 自動導航`) and **Camera Tracking** (`🎯 鏡頭跟隨`) are visible as readable icon-plus-text pill buttons while hiding the 5 unused legacy controls; and restyle the top-right Speed Control and **Auto Navigation** HUD floating cards with a dedicated blossom-pink active theme (`#F299B1` / `#E8829C`) when **Planting Speed** (`🌸 種花 19.1 km/h`) is selected.

**Blocked by:** 01: Bento 工作台骨架、深淺色植栽主題與「🌸 花徑漫步」全頁中文化

**Status:** completed

- [x] Set `CartoDB Voyager` as the default initial tile layer on map startup while preserving all other base layers in the layer switcher control, and style the **Auto Navigation** route polyline in soft botanical sage green (`#6B9E78`, rounded caps/joins).
- [x] Hide the unused top-left toolbar controls (GPX file upload, GeoJSON save, GPX playback, polyline draw, legacy speed menu, and clear markers trash icon) via CSS while preserving their DOM elements so legacy script references remain error-free.
- [x] Upgrade the visible **Auto Navigation** (`#autoNavButton`) and **Camera Tracking** (`#cameraFollowButton`) controls into rounded icon-plus-text pill buttons (`🧭 自動導航` and `🎯 鏡頭跟隨`) that preserve their required icon classes and highlight with botanical theme colors when active.
- [x] Restyle the top-right Speed Control card (`#speedControlWidget`) and **Auto Navigation** HUD card (`#navigationHud`) as rounded floating islands with friendly Traditional Chinese preset labels (`🚶 散步`, `🌸 種花`, `🚗 開車`) while maintaining backward-compatible preset text/attributes for existing tests.
- [x] Toggle a `.planting-mode-active` state on the speed control widget and speed badge when **Planting Speed** (`19.1 km/h`) is active so the preset button, badge, and slider highlight in blossom pink (`#E8829C` / `#F299B1`), and verify all existing and new frontend/Node.js tests pass.
