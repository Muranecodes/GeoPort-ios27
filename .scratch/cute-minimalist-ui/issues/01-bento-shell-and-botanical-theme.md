# 01: Bento 工作台骨架、深淺色植栽主題與「🌸 花徑漫步」全頁中文化

**What to build:** Rebrand the web workbench to **「🌸 花徑漫步」** (without a subtitle), remove the obsolete secondary HTML template and duplicate Bootstrap 4 stylesheet, and restructure the page into a non-scrolling Three-Tier Compact Bento Card layout powered by a Japanese botanical color system (Warm Cream `#FAF8F5` with Sage Green `#6B9E78` and Blossom Pink `#E8829C` in light mode, and Cozy Forest Night `#1E2522` / `#28312C` in dark mode). Unify all header, device connection, coordinate search, **Location Simulation**, context-menu, toast, and modal copy into friendly Traditional Chinese while keeping all existing DOM IDs and `localStorage` keys intact.

**Blocked by:** None (can start immediately)

**Status:** completed

- [x] Remove the unused secondary map template from the repository and eliminate the duplicate Bootstrap 4 CSS import so styling is governed cleanly by Bootstrap 5 and custom botanical CSS variables.
- [x] Define CSS custom properties for Light Mode (Warm Cream `#FAF8F5`, pure cream cards, Sage Green `#6B9E78`, Blossom Pink `#E8829C`, rounded sans-serif typography, `20px–24px` card corners, and `999px` pill buttons) and Dark Mode (`body.dark-mode` with Cozy Forest Night `#1E2522` background and `#28312C` card surfaces).
- [x] Restructure the page into a single-viewport Three-Tier Compact Bento Card layout:
  - Top Bento Card (single horizontal row): Brand title `🌸 花徑漫步`, inline device selector (`📱 選擇裝置`), refresh button (`🔄 重新整理`), connect/disconnect buttons (`🔗 連線裝置` / `🔌 中斷連線`), dark mode switch (`🌙 深色模式`), and exit button (`🚪 離開`).
  - Center Map Canvas Card: Rounded map container (`24px` border radius) that flexes to fill remaining viewport height without vertical page scrolling.
  - Bottom Bento Card (single horizontal row): Coordinate/place search input (`🔍 輸入座標或地名…`), search button (`搜尋`), and **Location Simulation** pill buttons (`📍 開始定位` and `🛑 停止定位`).
- [x] Localize all user-facing messages, right-click starting-point popup (`📌 設為預設起點`), toast headers (`🌸 花徑漫步`), connection states (`連線中，請稍候…` / `✅ 已連線`), and system modals (Developer Mode, passcode prompt, pair record prompt, connection timeout, server shutdown) into friendly Traditional Chinese.
- [x] Add automated tests verifying the rendered `🌸 花徑漫步` brand identity, Three-Tier Bento structure, Traditional Chinese UI copy, dark mode theme variables, preservation of all existing DOM IDs, and removal of the obsolete secondary template.
