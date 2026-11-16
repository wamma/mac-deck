# Feature preservation

This public distribution preserves the implementation features of the private source snapshot. It does not claim that previously unverified provider or device behavior is complete.

| Feature | Retained implementation | Public changes / limitations | Final verification / status |
|---|---|---|---|
| App switching, custom apps and order | native activation, app editor, saved settings | Verified activation unchanged; toast suppressed | test_core/test_app_order/test_actions; OS switching not repeated |
| System controls | screenshot shortcut, volume/mute, brightness, copy/paste | OS permissions and hardware support required | test_system/test_native_target; real hardware not repeated |
| Clipboard history | memory-only capture, pause, search, restore helpers | OFF by default; never exported | test_core/test_web_text_verifier; named fixture pasteboard only |
| Text and URL macros | Unicode + Enter, single/multiple URLs | Existing target verification and no retry | test_actions/test_http/test_native_target; real input not repeated |
| Trash confirmation | server confirmation nonce and three-second window | Unchanged; never test with user trash | test_actions/test_http; isolated confirmation fixtures |
| Manual AI slots | session IDs, proof, window mapping, one-shot reply | Actual provider/window permissions still required | test_ai/test_ai_tasks/test_http; real capture/reply remains unverified |
| Orca active list | recent actual activity, maximum twelve | Official metadata only; read-only details | test_orca_activity; synthetic metadata, no live provider query |
| Usage and weather | provider readers and location UI | Missing provider supported; actual Claude usage not established | test_sources/test_discovery/test_claude_usage; actual Claude receipt unverified |
| Touch reorder | tile long press and persistent order | No forced order on reconnect | Retained source; historical touch tests retained, no new physical-device claim |
| Web power saving | thirty seconds idle, wake-only first input | Browser black overlay, not OS screen-off | Retained source; no new physical battery/IME claim |
| Arc tab list | running-app PID read, windows, search, manual refresh | Read-only; no tab selection/closure | test_arc_tabs/test_http; synthetic UI, no live browser metadata read |
| Automatic server replacement | exact process/script/data-dir/endpoint checks | Never replaces the private repository server | test_startup/test_public_security; real isolated process tests |
| All native/scripts/assets/tests | exported from tracked source files | Personal evidence removed; verification paths configurable | Source inventory and syntax/build checks; live scripts are opt-in |
| Transport and access | TLS, local pairing window, session revocation | New public hardening, verified separately | test_public_security real loopback TLS/admission/concurrency; mobile trust unverified |

Security does not make paired clients read-only: a paired device can control the Mac. Do not expose this service to the public Internet.
